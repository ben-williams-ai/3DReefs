# Implementation Plan: Camera Selection V2

**Branch**: `008-camera-selection-v2` | **Date**: 2026-06-17 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/006-hybrid-camera-selection/spec.md`

## Summary

Replace the current patch camera selector with one production selector that
scores internal and external cameras against a scene-scaled, aspect-aware patch
footprint target. The selector keeps COLMAP track evidence, projected footprint
evidence, target-image-share checks, azimuth diversity as a small tie-break, and
diagnostics. It removes fixed target grids, early stopping while useful
candidates remain, and any separate buffer-biased ranking.

Feature acceptance is diagnostics-only: no splat training, merge, or SOG export
is required to accept this feature.

## Technical Context

**Language/Version**: Python 3.12+  
**Primary Dependencies**: Existing project dependencies only: `numpy`,
`matplotlib`, `pycolmap` where already used, and standard-library helpers. No
new dependency for the selector.  
**Storage**: Filesystem patch artefacts under `project.dir/runs/<run_id>/splat/patches/`.  
**Testing**: `pytest` unit and integration tests; scratch diagnostic comparisons
for known reef and Polish-town style patches.  
**Target Platform**: Ubuntu workstation running the existing 3DReefs CLI.  
**Project Type**: Python CLI/application package.  
**Performance Goals**: Patch selection should remain small compared with LFS
training time; diagnostics-only validation must not launch LFS.  
**Constraints**: One selector only; no public selector-mode config; no new
production dependency; no source SfM or image mutation; all reuse/overwrite
decisions remain up front.  
**Scale/Scope**: Thousands of registered images, patch camera caps commonly in
the 400-1200 range, low-texture reef areas, and Polish-town style oblique or
vertical structure.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Reproducible Pipeline Runs**: PASS. Selector name/version, settings,
  source sparse reference, selected counts, warnings, and diagnostics are
  recorded in patch artefacts and run records.
- **Observable Long-Running Work**: PASS. Patch diagnostics expose camera
  decisions before expensive training.
- **Explicit Resume And Overwrite Behaviour**: PASS. Incompatible selector
  outputs are decided before patching starts.
- **Modular, Testable Implementation**: PASS. Target sampling, projection,
  scoring, selection, validation, and diagnostics remain importable helpers.
- **External Tool Validation**: PASS. No new external executable is introduced.
- **Data Safety**: PASS. Source sparse models and images are read-only; public
  docs use project-relative paths.

## Project Structure

### Documentation (this feature)

```text
specs/006-hybrid-camera-selection/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── diagnostics.md
│   ├── patch-selection-artifacts.md
│   └── run-records.md
└── tasks.md
```

### Source Code (repository root)

```text
src/reefs/
├── diagnostics/
│   └── patch_plots.py
├── patches/
│   ├── artefacts.py
│   ├── bounds.py
│   ├── export.py
│   ├── selection.py
│   ├── validation.py
│   └── visibility.py
└── splat/
    ├── pipeline.py
    └── resume.py

tests/
├── fixtures/
│   ├── patch_selection.py
│   └── patch_selection_paths.py
├── integration/
│   └── test_splat_hybrid_camera_selection.py
└── unit/
    ├── test_patch_selection.py
    ├── test_patch_selection_diagnostics.py
    ├── test_patch_validation.py
    └── test_patch_visibility.py
```

**Structure Decision**: Keep selector logic in `src/reefs/patches/`.
`visibility.py` owns footprint samples, projection helpers, target image share,
and height sampling. `selection.py` owns candidate discovery, scoring, marginal
selection, warnings, and selector metadata. Diagnostics stay in
`src/reefs/diagnostics/patch_plots.py`. CLI and splat orchestration stay thin.

## Complexity Tracking

No constitution violations or justified complexity exceptions.

## Phase 0: Research Summary

See [research.md](research.md). Resolved decisions:

- Use one production selector: scene-scaled footprint target plus marginal
  camera selection.
- Allocate target cells from total registered images and patch area.
- Use a tiny minimum target-cell count so very small patches still have a
  footprint representation.
- Use aspect-aware target cells across the whole stored patch footprint.
- Use adaptive per-cell heights from local or neighbouring sparse points, with
  robust fallback heights for empty cells.
- Treat either matched tracks or geometric footprint visibility as enough to
  make a camera useful.
- Use target image share to reduce tiny-sliver selections.
- Use one-ring neighbours plus direct target evidence for external candidates.
- Use azimuth diversity only as a small tie-break.
- Validate with patch diagnostics only.

## Phase 1: Design Summary

See:

- [data-model.md](data-model.md)
- [contracts/diagnostics.md](contracts/diagnostics.md)
- [contracts/patch-selection-artifacts.md](contracts/patch-selection-artifacts.md)
- [contracts/run-records.md](contracts/run-records.md)
- [quickstart.md](quickstart.md)

## Post-Design Constitution Check

- **Reproducible Pipeline Runs**: PASS. Selector provenance and patch-affecting
  settings are part of metadata and reuse checks.
- **Observable Long-Running Work**: PASS. Every generated patch has diagnostic
  CSV/log/plot artefacts where possible.
- **Explicit Resume And Overwrite Behaviour**: PASS. Selector version/signature
  incompatibility is an up-front decision.
- **Modular, Testable Implementation**: PASS. The design splits sampling,
  projection, selection, validation, and diagnostics into focused helpers.
- **External Tool Validation**: PASS. No new executable or backend is added.
- **Data Safety**: PASS. Source SfM outputs are read-only.
