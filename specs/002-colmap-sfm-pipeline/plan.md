# Implementation Plan: COLMAP SfM Pipeline

**Branch**: `002-colmap-sfm-pipeline` | **Date**: 2026-06-10 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/002-colmap-sfm-pipeline/spec.md`

## Summary

Build the second pipeline slice on top of Feature 1: the COLMAP SfM workflow from
project-local raw images through sparse reconstruction and undistorted outputs
ready for later splatting. The implementation extends the existing `uv run
main.py --config ...` entrypoint, config models, run records, timing capture,
resume/overwrite decisions, and external-tool validation. It adds COLMAP-specific
preflight checks, intrinsics handling, feature extraction, matching,
reconstruction, undistortion, optional dense/mesh outputs, and `logs/colmap.log`.

The current guide in `scratch/setup/old_pipeline_notes_updated_for_speckit.MD` is
the source of truth. The old `3D-Reefs/glomap` repo is evidence for useful command
shape, validation patterns, and historical defaults only; it must not be copied
as architecture and its legacy standalone GLOMAP path is out of scope.

## Technical Context

**Language/Version**: Python 3.12+  
**Primary Dependencies**: Existing `click`, `pydantic`, `PyYAML`, standard `subprocess`, `sqlite3`, `pathlib`, `csv`, `json`; no new required runtime dependency planned. Image metadata/dimension checks should first use standard-library or already-available mechanisms; add a dependency only if implementation proves it is necessary and record the decision.  
**Storage**: Filesystem-only run records under `project.dir/runs/<run_id>/`; COLMAP database and outputs under the active run directory.  
**Testing**: `pytest` unit and integration tests. Mock COLMAP for automated command, status, and failure tests; use local ignored `data/test_dataset` only for optional/manual smoke checks.  
**Target Platform**: Ubuntu Linux workstation with NVIDIA GPU; COLMAP target version `4.0.4`.  
**Project Type**: Python CLI/application package.  
**Performance Goals**: Fail invalid configs, missing vocabulary tree, invalid image layout, invalid camera files, and unsupported backends before feature extraction; record exact duration for every SfM substage that runs; avoid avoidable work when resume/reuse is selected.  
**Constraints**: Do not modify raw images in place; no legacy standalone GLOMAP backend; no silent fallback between global/incremental reconstruction or selected matching modes; all resume/reuse/rerun/overwrite and mixed-camera-source decisions happen during preflight; public docs/configs use placeholders, not private paths.  
**Scale/Scope**: Reef datasets from small smoke fixtures through thousands of images; feature includes SfM, undistortion, optional dense/mesh only, and excludes all splatting stages.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Reproducible Pipeline Runs**: PASS. The plan extends Feature 1 run records with
  SfM-specific config, CLI overrides, selected sparse model metadata, tool checks,
  and output paths.
- **Observable Long-Running Work**: PASS. COLMAP command stdout/stderr goes to
  `logs/colmap.log`; timings cover preflight, intrinsics, feature extraction,
  each matching pass, reconstruction, undistortion, dense, and mesh stages.
- **Explicit Resume And Overwrite Behaviour**: PASS. Prior outputs are inspected
  before any requested SfM stage starts; all reuse/rerun/overwrite and
  mixed-camera-source decisions are gathered up front.
- **Modular, Testable Implementation**: PASS. Reusable SfM, COLMAP, diagnostics,
  and config logic will live under `src/reefs/`; CLI remains orchestration only;
  command construction and status detection receive focused tests.
- **External Tool Validation**: PASS. COLMAP `4.0.4`, selected COLMAP commands,
  GPU-capable flags where possible, reconstruction backend, and vocabulary tree
  resources are validated before heavy work.
- **Data Safety**: PASS. Raw images and recoloured images are read-only; generated
  artefacts live under run directories; public examples use placeholders.

## Project Structure

### Documentation (this feature)

```text
specs/002-colmap-sfm-pipeline/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── cli.md
│   ├── config-schema.yml
│   ├── colmap-commands.md
│   └── run-records.md
└── tasks.md
```

### Source Code (repository root)

```text
main.py
configs/
├── example.yml
└── datasets/
src/
└── reefs/
    ├── cli.py
    ├── colmap/
    │   ├── __init__.py
    │   ├── commands.py
    │   ├── database.py
    │   ├── models.py
    │   ├── outputs.py
    │   └── runner.py
    ├── config/
    │   ├── loader.py
    │   ├── models.py
    │   └── overrides.py
    ├── diagnostics/
    │   ├── __init__.py
    │   ├── cameras.py
    │   └── images.py
    ├── io/
    ├── logging/
    ├── preflight/
    │   ├── images.py
    │   ├── sfm.py
    │   └── tools.py
    ├── runs/
    └── sfm/
        ├── __init__.py
        ├── intrinsics.py
        ├── pipeline.py
        ├── resume.py
        └── validation.py
tests/
├── unit/
│   ├── test_colmap_commands.py
│   ├── test_colmap_outputs.py
│   ├── test_sfm_config.py
│   ├── test_sfm_intrinsics.py
│   ├── test_sfm_preflight.py
│   └── test_sfm_resume.py
└── integration/
    ├── test_sfm_mocked_success.py
    ├── test_sfm_mocked_failures.py
    ├── test_sfm_recoloured_undistortion.py
    └── test_sfm_partial_outputs.py
```

**Structure Decision**: Keep `main.py` and `src/reefs/cli.py` thin. Put reusable
COLMAP command construction and bounded execution in `src/reefs/colmap/`, SfM
stage orchestration in `src/reefs/sfm/`, image/camera diagnostics in
`src/reefs/diagnostics/`, and preflight glue in `src/reefs/preflight/sfm.py`.
This extends Feature 1 rather than creating a separate old-style runner.

## Complexity Tracking

No constitution violations or complexity exceptions are required.

## Phase 0: Research Summary

See [research.md](research.md). Key resolved decisions:
- Extend the existing run directory with `sfm/`, `logs/colmap.log`, and
  diagnostics, rather than creating separate project-level SfM output roots.
- Treat the vocabulary tree as a required configured resource whenever selected
  matching uses vocabulary-tree retrieval.
- Use a COLMAP command builder with explicit option mapping and help-output
  validation rather than ad hoc string assembly.
- Implement default intrinsics pre-calculation as a selected-image subset
  reconstruction with intrinsics refinement enabled; pass the estimated OPENCV
  camera parameters into the full feature extraction and keep final
  reconstruction intrinsics refinement disabled by default.
- Select the sparse model with the most registered images when multiple models
  are produced, recording registered image and 3D point counts for all models.
- Keep dense and mesh disabled by default and require explicit enablement.

## Phase 1: Design Summary

See:
- [data-model.md](data-model.md)
- [contracts/cli.md](contracts/cli.md)
- [contracts/config-schema.yml](contracts/config-schema.yml)
- [contracts/colmap-commands.md](contracts/colmap-commands.md)
- [contracts/run-records.md](contracts/run-records.md)
- [quickstart.md](quickstart.md)

## Post-Design Constitution Check

- **Reproducible Pipeline Runs**: PASS. Contracts require effective config,
  selected stage decisions, selected sparse model statistics, and SfM output paths.
- **Observable Long-Running Work**: PASS. Command logs, warning records, timings,
  and diagnostics are explicitly specified.
- **Explicit Resume And Overwrite Behaviour**: PASS. CLI and run-record contracts
  require decisions before any requested SfM stage starts.
- **Modular, Testable Implementation**: PASS. Planned modules isolate config,
  preflight, command construction, execution, output selection, and resume logic.
- **External Tool Validation**: PASS. Backend, matching resources, and command
  availability are preflight requirements.
- **Data Safety**: PASS. Source images are read-only; public paths remain
  placeholders.
