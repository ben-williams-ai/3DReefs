# Implementation Plan: Pipeline Foundation

**Branch**: `001-pipeline-foundation` | **Date**: 2026-06-10 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/001-pipeline-foundation/spec.md`

## Summary

Build the first reusable slice of the 3DReefs pipeline: a `uv`-run CLI that loads
and validates a config, derives project-local input/output paths from
`project.dir`, applies CLI overrides, validates external tool paths/versions
without running heavy work, creates auditable run records, and handles partial-run
resume/start-over decisions before any stage executes.

The CLI should reserve the full-pipeline shape now: `main.py` runs all configured
steps by default in later features, `--steps` limits the requested steps, and
`--resume-policy` supplies explicit non-interactive resume/overwrite intent. In
Feature 1 those values are validated, recorded, and used for preflight decisions
only; no heavy stage is executed.

The old 3D-Reefs GLOMAP repo is evidence for useful
behaviours such as project-local outputs, binary flag audits, and timing parsing,
but the new implementation follows
`scratch/setup/old_pipeline_notes_updated_for_speckit.MD` as the source of truth
and does not copy the old runner architecture.

## Technical Context

**Language/Version**: Python 3.12+  
**Primary Dependencies**: `click` for the CLI parser, `pydantic` for typed config models, `PyYAML` for YAML IO, standard `subprocess` for bounded tool validation  
**Storage**: Filesystem-only JSON/YAML/Markdown/log files under `project.dir/runs/<run_id>/`  
**Testing**: `pytest` unit and integration tests, with external tool calls mocked for most tests  
**Target Platform**: Ubuntu Linux workstation with NVIDIA GPU; Feature 1 does not require GPU execution  
**Project Type**: Python CLI/application package  
**Performance Goals**: Foundation checks on a valid small project complete in under 5 seconds excluding external `--version`/help command latency; external validation commands have short timeouts and never start heavy processing  
**Constraints**: Do not run COLMAP reconstruction, matching, undistortion, patching, LFS training, cleanup, compression, or merge in this feature; do not write private dataset paths into tracked public example configs; fail on unknown config override keys  
**Scale/Scope**: Config/run foundation for large reef datasets, including future runs with thousands of images and many patch jobs; this feature only inspects path layout and records run metadata

Path override boundary: normal paths are derived from `project.dir`. Advanced path
overrides exist only to rename project-local folders or support local experiments;
relative override values resolve under `project.dir`, and public configs must not
use private absolute dataset paths.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Reproducible Pipeline Runs**: PASS. Plan records source config, effective config,
  CLI overrides, tool versions, and run manifest for every invocation.
- **Observable Long-Running Work**: PASS. Feature 1 creates the logging/timing/status
  substrate that later stages use, even though it does not run long COLMAP/LFS work.
- **Explicit Resume And Overwrite Behaviour**: PASS. Partial-run detection,
  non-interactive fail-fast behaviour, config diffing, and explicit decisions are
  central design requirements.
- **Modular, Testable Implementation**: PASS. Reusable logic is planned under
  `src/reefs/`; CLI remains thin; tests cover config parsing, path resolution,
  command construction, output selection, and resume logic.
- **External Tool Validation**: PASS. COLMAP, LFS, and SOG conversion validation are
  explicit bounded checks with no silent fallback.
- **Data Safety**: PASS. Raw images are read-only; public configs use placeholders;
  destructive overwrite requires explicit intent.

## Project Structure

### Documentation (this feature)

```text
specs/001-pipeline-foundation/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── cli.md
│   ├── config-schema.yml
│   └── run-records.md
└── tasks.md
```

### Source Code (repository root)

```text
main.py
pyproject.toml
uv.lock
configs/
├── example.yml
└── datasets/
    ├── dataset_01.yml
    ├── dataset_02.yml
    ├── dataset_03.yml
    ├── dataset_04.yml
    └── dataset_05.yml
src/
└── reefs/
    ├── __init__.py
    ├── cli.py
    ├── config/
    │   ├── __init__.py
    │   ├── loader.py
    │   ├── models.py
    │   └── overrides.py
    ├── io/
    │   ├── __init__.py
    │   ├── paths.py
    │   └── yaml_json.py
    ├── logging/
    │   ├── __init__.py
    │   ├── run_logger.py
    │   └── timings.py
    ├── preflight/
    │   ├── __init__.py
    │   ├── images.py
    │   ├── tools.py
    │   └── validation.py
    └── runs/
        ├── __init__.py
        ├── manifest.py
        ├── resume.py
        └── status.py
tests/
├── unit/
│   ├── test_config_loader.py
│   ├── test_cli_overrides.py
│   ├── test_project_paths.py
│   ├── test_resume_decisions.py
│   └── test_tool_validation.py
└── integration/
    ├── test_foundation_valid_project.py
    ├── test_foundation_recoloured_layout.py
    └── test_foundation_partial_run.py
```

**Structure Decision**: Use a conventional `src/reefs/` Python package so tests
import the installed package namespace instead of repo-root modules. Keep
`main.py` as a thin entrypoint delegating to `reefs.cli`.

## Complexity Tracking

No constitution violations or complexity exceptions are required.
