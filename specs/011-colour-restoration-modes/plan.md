# Implementation Plan: Colour Restoration Modes

**Branch**: `011-colour-restoration-modes` | **Date**: 2026-06-23 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/011-colour-restoration-modes/spec.md`

## Summary

Replace the old `project.recolour_images` boolean with a required top-level `colour_restoration` block whose `mode` selects `off`, `gray_world`, or `manual`, whose `overwrite` flag controls same-run restored image reuse for automatic and manual outputs, and whose `start_sfm_immediately` setting preserves the existing manual GUI/SfM overlap behaviour. The implementation will add typed config models, remove legacy project-level colour settings, extend the existing `reefs.colour` orchestration to support an unattended gray-world mode, and update SfM/splat handoff checks so raw, automatic, and manual modes never silently fall back across one another.

## Technical Context

**Language/Version**: Python >=3.12  
**Primary Dependencies**: Existing `click`, `pydantic`, `pyyaml`, `pycolmap`, `PySide6`, `numpy`, `Pillow`, `torch`, and `wildflow`; no new dependency required.  
**Storage**: YAML config files; restored images under the configured `recoloured_images/` tree; run colour state JSON under `<project.dir>/runs/<run_id>/colour_restoration/state.json`; existing run manifests/status/timings/log files.  
**Testing**: `uv run pytest` with focused unit and integration coverage under `tests/unit/` and `tests/integration/`; final verification with `uv run pytest tests`.  
**Target Platform**: Ubuntu/Linux workstation with local filesystem image datasets; graphical desktop session required only for `colour_restoration.mode: manual` and `colour open`.  
**Project Type**: Python CLI pipeline with desktop GUI workflow and external COLMAP/LFS tool integration.  
**Performance Goals**: `off` mode adds no colour state/output work; `gray_world` writes one full-resolution restored RGB image per source image with bounded worker parallelism; manual behaviour remains no slower than the current GUI/apply workflow.  
**Constraints**: Never modify raw images; require the top-level `colour_restoration` block; fail clearly for legacy `project.recolour_images` and `project.start_sfm_immediately`; reuse same-run restored images only when mode/state compatibility is explicit; overwrite restored outputs only through the configured explicit overwrite path; no silent fallback between modes.  
**Scale/Scope**: Existing single- and multi-camera datasets from hundreds to tens of thousands of images; all maintained example, dataset, and test configs; existing colour CLI and pipeline routes.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Reproducible Pipeline Runs**: PASS. Plan records the selected colour restoration block values in effective config and colour state/manifest fields.
- **II. Observable Long-Running Work**: PASS. Gray-world apply and manual apply continue to report progress, completion/failure, and state status.
- **III. Explicit Resume And Overwrite Behaviour**: PASS. Same-run restored output reuse defaults to `overwrite: false`; replacement requires `overwrite: true` and incompatible outputs fail rather than being adopted.
- **IV. Modular, Testable Implementation**: PASS. Behaviour is split across typed config models, `reefs.colour` orchestration, and thin CLI/pipeline hooks with focused tests.
- **V. External Tool Validation**: PASS. Existing COLMAP/LFS validation remains; colour mode selection never silently changes requested external-tool stages.
- **VI. Data Safety**: PASS. Raw images remain read-only inputs; public docs/configs use placeholders and no private paths.

## Project Structure

### Documentation (this feature)

```text
specs/011-colour-restoration-modes/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── cli.md
│   ├── colour-state.schema.json
│   └── config-schema.yml
└── tasks.md
```

### Source Code (repository root)

```text
src/reefs/
├── colour/
│   ├── filters.py
│   ├── pipeline.py
│   └── state.py
├── cli.py
├── config/
│   ├── loader.py
│   ├── models.py
│   └── overrides.py
├── preflight/
│   ├── sfm.py
│   └── splat.py
└── sfm/pipeline.py

tests/
├── conftest.py
├── unit/
│   ├── test_config_loader.py
│   ├── test_config_models.py
│   └── test_splat_config.py
└── integration/
    ├── test_colour_apply.py
    ├── test_colour_cli.py
    ├── test_colour_disabled_pipeline.py
    ├── test_colour_reuse.py
    ├── test_sfm_recoloured_undistortion.py
    └── test_splat_colour_wait.py

README.MD
configs/example.yml
configs/test.yml
configs/datasets/*.yml
```

**Structure Decision**: Keep the existing single Python package layout. Add typed colour restoration configuration in `src/reefs/config/models.py`, update existing `reefs.colour` orchestration for automatic mode/reuse semantics, and adjust current CLI/preflight/SfM handoff code rather than creating a parallel pipeline.

## Phase 0: Research

See [research.md](research.md). All technical unknowns are resolved there; no `NEEDS CLARIFICATION` items remain.

## Phase 1: Design And Contracts

- Data model: [data-model.md](data-model.md)
- Config contract: [contracts/config-schema.yml](contracts/config-schema.yml)
- CLI contract: [contracts/cli.md](contracts/cli.md)
- Colour state contract: [contracts/colour-state.schema.json](contracts/colour-state.schema.json)
- Quickstart: [quickstart.md](quickstart.md)

## Constitution Check (Post-Design)

- **I. Reproducible Pipeline Runs**: PASS. Data model and contracts include effective config, mode, overwrite, start-SfM behaviour, output source, and state metadata.
- **II. Observable Long-Running Work**: PASS. Contracts require state transitions and progress/failure visibility for automatic and manual apply paths.
- **III. Explicit Resume And Overwrite Behaviour**: PASS. Contracts make `overwrite` the only regeneration switch for same-run restored outputs and reject incompatible reuse.
- **IV. Modular, Testable Implementation**: PASS. Tasks will target focused config, colour pipeline, CLI, SfM, and splat modules with unit/integration tests.
- **V. External Tool Validation**: PASS. Plan keeps external tool validation unchanged and mode-specific failures explicit.
- **VI. Data Safety**: PASS. Contracts forbid raw image mutation and require restored output validation before downstream use.

## Complexity Tracking

No constitution violations require justification.
