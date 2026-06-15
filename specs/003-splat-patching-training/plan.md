# Implementation Plan: Splat Patching And Training

**Branch**: `003-splat-patching-training` | **Date**: 2026-06-11 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/003-splat-patching-training/spec.md`

## Summary

Build the third pipeline slice on top of Feature 1 run records and Feature 2
COLMAP outputs: validate undistorted SfM artefacts, filter camera pose outliers,
generate trainable patch datasets with view-based camera selection, and train
LichtFeld Studio splats one patch at a time. The implementation extends the
existing `uv run main.py --config ...` entrypoint and `project.dir/runs/<run_id>/`
run-record model. Patch cleanup, cleaned patch merging, final SOG conversion,
NanoGS, LOD, PlayCanvas, and mega-patching remain out of scope.

The current guide in `scratch/setup/old_pipeline_notes_updated_for_speckit.MD`
is the source of truth. The old patching and splat-training code is evidence for
useful algorithms and historical defaults only; it must not be copied as the new
architecture.

## Technical Context

**Language/Version**: Python 3.12+  
**Primary Dependencies**: Existing `click`, `pydantic`, `PyYAML`; add `pycolmap` for robust COLMAP sparse model read/write/subset export; add `wildflow` for patch extent generation; add `matplotlib` for non-interactive diagnostics plots; use standard `subprocess`, `tempfile`, `pathlib`, `csv`, `json`, and `shutil` for orchestration and records.  
**Storage**: Filesystem-only run records under `project.dir/runs/<run_id>/`; patching and training outputs under the active run's `splat/` directory.  
**Testing**: `pytest` unit and integration tests. Mock LFS for automated command/status tests; use local ignored `data/test_dataset` for manual smoke checks after implementation.  
**Target Platform**: Ubuntu Linux workstation with NVIDIA GPU; LichtFeld Studio target version `v0.5.2`; Feature 2 COLMAP outputs from COLMAP `4.0.4`.  
**Project Type**: Python CLI/application package.  
**Performance Goals**: Fail missing or incompatible SfM/patch/training inputs before expensive LFS work; validate checkable splat dependencies during the earliest applicable preflight; train exactly one patch at a time; record timings for outlier filtering, patch generation, and every requested patch training job.  
**Constraints**: Do not modify raw images or the only SfM output copy in place; all resume/reuse/overwrite/skip decisions happen before requested stages start; no multi-patch LFS parallelism; no point-cloud downsampling or target-bin patch options; no metric "metres" terminology for scene-relative patch buffers.  
**Scale/Scope**: Small smoke datasets through thousands of reef images; patch size is set by the user through maximum cameras per patch, and the user is responsible for choosing a value that fits their GPU memory and image dimensions; this feature stops after patch training status and splat artefacts.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Reproducible Pipeline Runs**: PASS. Patching and training extend the existing
  run manifest, effective config, CLI override, and run status records.
- **Observable Long-Running Work**: PASS. Patching, outlier filtering, LFS
  command output, warnings, patch status, and timings are explicitly recorded.
- **Explicit Resume And Overwrite Behaviour**: PASS. Existing patch/training
  outputs are inspected and resolved before any requested stage starts.
- **Modular, Testable Implementation**: PASS. Reusable behaviour will live under
  `src/reefs/splat/`, `src/reefs/patches/`, `src/reefs/lfs/`,
  `src/reefs/diagnostics/`, and `src/reefs/preflight/`; CLI remains thin.
- **External Tool Validation**: PASS. Feature 1 tool path resolution is reused;
  pycolmap is validated during global/splat preflight whenever splat stages are
  requested or enabled, and LFS is validated up front when training is requested.
- **Data Safety**: PASS. Inputs are read-only; filtered reconstructions and patch
  sparse models are derived copies; public docs/configs use placeholders.

## Project Structure

### Documentation (this feature)

```text
specs/003-splat-patching-training/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── cli.md
│   ├── config-schema.yml
│   ├── lfs-training.md
│   ├── patch-artifacts.md
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
    ├── config/
    │   └── models.py
    ├── diagnostics/
    │   ├── patch_plots.py
    │   └── training.py
    ├── lfs/
    │   ├── __init__.py
    │   ├── commands.py
    │   ├── runner.py
    │   └── status.py
    ├── patches/
    │   ├── __init__.py
    │   ├── artefacts.py
    │   ├── bounds.py
    │   ├── export.py
    │   ├── outliers.py
    │   ├── selection.py
    │   └── validation.py
    ├── preflight/
    │   └── splat.py
    ├── runs/
    └── splat/
        ├── __init__.py
        ├── pipeline.py
        ├── resume.py
        └── validation.py
tests/
├── unit/
│   ├── test_lfs_commands.py
│   ├── test_lfs_status.py
│   ├── test_patch_bounds.py
│   ├── test_patch_outliers.py
│   ├── test_patch_reuse.py
│   ├── test_patch_selection.py
│   └── test_splat_config.py
└── integration/
    ├── test_splat_mocked_success.py
    ├── test_splat_mocked_failures.py
    ├── test_splat_partial_outputs.py
    └── test_splat_training_status.py
```

**Structure Decision**: Keep orchestration in `src/reefs/splat/pipeline.py`.
Patch dataset generation belongs in `src/reefs/patches/`; LFS command/status
handling belongs in `src/reefs/lfs/`; preflight checks belong in
`src/reefs/preflight/splat.py`; diagnostic plotting remains separate from core
patch logic. This keeps Feature 3 independent from later cleanup/merge/export
features.

## Complexity Tracking

No constitution violations or complexity exceptions are required.

## Phase 0: Research Summary

See [research.md](research.md). Key resolved decisions:
- Use pycolmap for sparse model read/write and patch subset export.
- Use a filtered reconstruction copy rather than mutating Feature 2 SfM outputs.
- Treat large proposed camera removals as ambiguous, not ordinary outlier
  removal.
- Generate wildflow birds-eye patch extents from the reconstruction, then perform
  final camera assignment with the view-based route only. The old code's
  relevant evidence is `select_by_views`: score candidate local/support cameras by
  visible sparse points inside the patch, projected image-space coverage,
  boundary coverage, median visible depth, and azimuth-sector balance, then
  export a sparse subset for the selected cameras. Birds-eye camera-centre
  membership is not the final assignment policy.
- Reuse valid existing patch datasets for training when only training settings
  changed.
- Train exactly one patch at a time and do not expose multi-patch parallelism.
- Parse LFS progress and classify patch status without requiring terminal-log
  inspection.

## Phase 1: Design Summary

See:
- [data-model.md](data-model.md)
- [contracts/cli.md](contracts/cli.md)
- [contracts/config-schema.yml](contracts/config-schema.yml)
- [contracts/patch-artifacts.md](contracts/patch-artifacts.md)
- [contracts/lfs-training.md](contracts/lfs-training.md)
- [contracts/run-records.md](contracts/run-records.md)
- [quickstart.md](quickstart.md)

## Post-Design Constitution Check

- **Reproducible Pipeline Runs**: PASS. Design records patch provenance,
  patch-affecting config hash/materialised settings, LFS command settings, and
  patch-level outputs.
- **Observable Long-Running Work**: PASS. Design requires stage timings,
  patch-level timings, LFS logs, warnings, skip records, and diagnostics.
- **Explicit Resume And Overwrite Behaviour**: PASS. Contracts require patch
  reuse/overwrite/skip decisions before patching/training work starts.
- **Modular, Testable Implementation**: PASS. Planned modules isolate config,
  validation, patch bounds, selection, export, LFS execution, status parsing, and
  run-record updates.
- **External Tool Validation**: PASS. pycolmap availability is checked during the
  earliest applicable preflight; LFS is checked before any training work; LFS
  failure modes are captured per patch.
- **Data Safety**: PASS. Source SfM and images are read-only; symlinks/copies are
  generated under run directories; public examples avoid private paths.
