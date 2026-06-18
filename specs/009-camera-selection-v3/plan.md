# Implementation Plan: Camera Selection V3

**Branch**: `009-camera-selection-v3` | **Date**: 2026-06-18 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/009-camera-selection-v3/spec.md`

## Summary

Replace the current old boundary-first patch camera selector with one V3 selector for Gaussian splat patching: patch bounds are generated with the internal camera target, useful internal cameras are kept first, neighbouring external cameras are optional capped support, and diagnostics explain the selected/rejected camera categories before any LFS training.

## Technical Context

**Language/Version**: Python 3.12 project run through `uv`  
**Primary Dependencies**: Existing project modules, `wildflow.splat.patches`, COLMAP text sparse inputs, matplotlib diagnostics, pytest  
**Storage**: File artefacts under the existing run directory: patch metadata JSON, sparse text subsets, selected-image links, CSV/PNG/HTML/log diagnostics  
**Testing**: `uv run pytest -q` plus diagnostics-only validation sweeps before LFS training  
**Target Platform**: Ubuntu/Linux workstation with configured COLMAP/LFS toolchain, but this feature's first validation avoids LFS execution  
**Project Type**: CLI pipeline with importable Python modules under `src/reefs/`  
**Performance Goals**: Selection must finish during patch generation for Dataset 1/Dataset 2 diagnostic sweeps without launching training; diagnostics must be cheap enough to review before LFS  
**Constraints**: Never exceed `advanced.splat.patching.max_cameras`; no non-neighbour external search; no new public private paths; no extra selector modes  
**Scale/Scope**: Existing test dataset, Dataset 1/Dataset 2 400-camera sweeps, and Polish Town first-20-patch diagnostic validation

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Reproducible Pipeline Runs**: PASS. V3 uses existing config, run records, patch metadata, and selector settings.
- **II. Observable Long-Running Work**: PASS. Diagnostics and warnings are first-class outputs; LFS is intentionally deferred until diagnostics pass.
- **III. Explicit Resume And Overwrite Behaviour**: PASS. Patch outputs remain routed through existing splat preflight/resume handling.
- **IV. Modular, Testable Implementation**: PASS. Reusable selector logic stays in `src/reefs/patches/selection.py`; orchestration stays in `src/reefs/splat/pipeline.py`; tests cover selector, config, bounds, diagnostics, and validation.
- **V. External Tool Validation**: PASS. Uses existing wildflow/COLMAP sparse input validation; first validation does not invoke LFS.
- **VI. Data Safety**: PASS. Raw images and SfM outputs are read-only; generated artefacts stay under run/scratch outputs and docs use placeholders or relative paths.

## Project Structure

### Documentation (this feature)

```text
specs/009-camera-selection-v3/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── config-and-diagnostics.md
└── tasks.md
```

### Source Code (repository root)

```text
src/reefs/
├── config/models.py
├── diagnostics/patch_plots.py
├── patches/
│   ├── bounds.py
│   ├── export.py
│   ├── selection.py
│   └── validation.py
└── splat/
    ├── pipeline.py
    └── resume.py

tests/
├── unit/
│   ├── test_patch_bounds.py
│   ├── test_patch_diagnostics.py
│   ├── test_patch_selection.py
│   ├── test_patch_validation.py
│   └── test_splat_config.py
└── integration/
```

**Structure Decision**: Use the existing single Python CLI/importable-module layout. Camera selection is shared patching behaviour, so it belongs in `src/reefs/patches/selection.py`; pipeline/config/diagnostics changes stay in their current neighbouring modules.

## Phase 0 Research Summary

See [research.md](research.md).

Key decisions:

- V3 replaces the current selector signature rather than adding a selector mode.
- Patch bounds use `internal_patch_target = max_cameras - floor(max_cameras * external_support_fraction)`.
- Camera usefulness has exactly three evidence signals: patch tracks, rectangle/frustum footprint overlap, and target image share from the projected intersection polygon.
- Sparse points provide track evidence and one representative patch-plane height; they do not define footprint overlap or target image share shapes.
- External support is restricted to one-ring neighbouring patches and capped by the configured allowance.
- Diagnostics keep existing filenames and add V3-specific columns/counts.

## Phase 1 Design Summary

See [data-model.md](data-model.md), [contracts/config-and-diagnostics.md](contracts/config-and-diagnostics.md), and [quickstart.md](quickstart.md).

Implementation slices:

1. Add `external_support_fraction` to splat patching config and persisted patch-affecting settings.
2. Compute external allowance/internal target in splat patch generation and pass the internal target to wildflow patch bounds.
3. Replace old boundary-first score records with V3 camera evidence records based on patch tracks plus rectangle/frustum geometry while preserving export and diagnostic filenames.
4. Update diagnostics and patch metadata validation for V3 counts, warnings, and selector signature.
5. Add focused unit tests and diagnostic-only validation scripts/commands for the requested sweeps and known bad cases.

## Post-Design Constitution Check

- **I. Reproducible Pipeline Runs**: PASS. Config and selector signature are persisted in patch metadata.
- **II. Observable Long-Running Work**: PASS. Per-patch CSV/PNG/HTML/log outputs, warnings, and summary CSV/review notes are planned.
- **III. Explicit Resume And Overwrite Behaviour**: PASS. Existing splat output decisions remain unchanged.
- **IV. Modular, Testable Implementation**: PASS. No one-off selector script is required for production logic; validation wrappers may live under `scripts/` or `scratch/` only for experiments.
- **V. External Tool Validation**: PASS. No new external tools are introduced.
- **VI. Data Safety**: PASS. Generated diagnostics do not modify source images or SfM outputs.

## Complexity Tracking

No constitution violations.
