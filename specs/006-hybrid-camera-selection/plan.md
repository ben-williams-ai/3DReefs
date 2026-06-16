# Implementation Plan: Hybrid Camera Selection

**Branch**: `006-hybrid-camera-selection` | **Date**: 2026-06-16 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/006-hybrid-camera-selection/spec.md`

## Summary

Replace the current old boundary-first patch camera selector with one production
selector: the Target-Aware Spatial Greedy selector. The selector uses COLMAP
track evidence where it exists, geometric projection of patch target samples
where tracks are weak, density weighting to reduce textured-cluster dominance,
target-image-share penalties to avoid halo-heavy views, small local acquisition
coverage protection to stop hollow reef patches, and view-direction diversity
bonuses to preserve useful oblique/boundary support.

This feature changes camera selection and diagnostics for splat patch generation
only. It does not change wildflow patch-bound generation, COLMAP SfM, LFS
training, cleanup, merge, or SOG compression.

## Technical Context

**Language/Version**: Python 3.12+  
**Primary Dependencies**: Existing `click`, `pydantic`, `PyYAML`, `pycolmap`,
`matplotlib`, and `wildflow`; standard-library `csv`, `json`, `math`,
`pathlib`, and `statistics` for scoring and artefacts. No new dependency is
planned for the selector.  
**Storage**: Filesystem-only run records and patch artefacts under
`project.dir/runs/<run_id>/`; camera-selection diagnostics under each patch's
`patch_diagnostics/` folder.  
**Testing**: `pytest` unit and integration tests, plus manual diagnostic smoke
runs on existing test/dataset run folders before retraining.  
**Target Platform**: Ubuntu Linux workstation using existing completed COLMAP
and patch-generation outputs.  
**Project Type**: Python CLI/application package.  
**Performance Goals**: Selection should run before expensive LFS work and remain
small compared with training time by using bounded target samples, candidate
prefiltering, and per-patch timings; validation must not start LFS.  
**Constraints**: Do not modify source SfM outputs or raw/undistorted images in
place; do not add a selector-mode switch; all reuse/overwrite decisions happen
before patch regeneration; stored patch bounds are the target region and are not
expanded again.  
**Scale/Scope**: Thousands of registered images, patch caps commonly between
400 and 1200 cameras, reef transects with weak sparse tracks, and oblique
urban/drone patches with strong boundary-support needs.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Reproducible Pipeline Runs**: PASS. Selector provenance, selector-affecting
  settings, coverage summaries, warnings, and CLI overrides remain captured in
  patch metadata and Feature 1 run records.
- **Observable Long-Running Work**: PASS. The design adds per-patch selector
  metrics, warnings, diagnostics, and timings before any downstream training.
- **Explicit Resume And Overwrite Behaviour**: PASS. Existing patch outputs from
  incompatible selector settings require an up-front reuse/overwrite decision.
- **Modular, Testable Implementation**: PASS. Visibility projection, scoring,
  greedy selection, diagnostics, and artefact validation are testable helpers
  under `src/reefs/patches/` and `src/reefs/diagnostics/`.
- **External Tool Validation**: PASS. No new external executable is introduced;
  existing pycolmap/wildflow validation remains in the earlier splat preflight.
- **Data Safety**: PASS. Source sparse models and images are read-only; public
  docs use project-relative placeholders only.

## Project Structure

### Documentation (this feature)

```text
specs/006-hybrid-camera-selection/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── cli.md
│   ├── diagnostics.md
│   ├── patch-selection-artifacts.md
│   └── run-records.md
└── tasks.md
```

### Source Code (repository root)

```text
src/
└── reefs/
    ├── diagnostics/
    │   └── patch_plots.py
    ├── patches/
    │   ├── artefacts.py
    │   ├── bounds.py
    │   ├── export.py
    │   ├── selection.py
    │   ├── validation.py
    │   └── visibility.py
    ├── runs/
    └── splat/
        ├── pipeline.py
        └── resume.py

tests/
├── integration/
│   └── test_splat_hybrid_camera_selection.py
└── unit/
    ├── test_patch_selection.py
    ├── test_patch_selection_diagnostics.py
    ├── test_patch_selection_reuse.py
    └── test_patch_visibility.py
```

**Structure Decision**: Keep patch selection in `src/reefs/patches/`.
Projection and target-sample helpers may live in `visibility.py` so
`selection.py` stays readable. Diagnostics remain in
`src/reefs/diagnostics/patch_plots.py`. The CLI and splat pipeline continue to
call the patching stage; they should not grow selector-specific branching.

## Complexity Tracking

No constitution violations or complexity exceptions are required.

## Phase 0: Research Summary

See [research.md](research.md). Key resolved decisions:
- Use the Target-Aware Spatial Greedy selector as the single production selector.
- Use stored patch bounds as the target region and do not add a second buffer.
- Use bounded target samples plus robust patch Z as the initial target proxy.
- Combine COLMAP track evidence and geometric projection evidence with either-signal
  fusion.
- Use density weighting so raw sparse-point counts do not let textured clusters
  dominate.
- Select cameras greedily by marginal coverage gain rather than fixed support
  quotas or boundary-first ranking.
- Keep target-image-share and nonlocal/support status as soft penalties, not
  hard exclusions.
- Warn, but still write trainable patch outputs, when selector coverage is poor.

## Phase 1: Design Summary

See:
- [data-model.md](data-model.md)
- [contracts/cli.md](contracts/cli.md)
- [contracts/diagnostics.md](contracts/diagnostics.md)
- [contracts/patch-selection-artifacts.md](contracts/patch-selection-artifacts.md)
- [contracts/run-records.md](contracts/run-records.md)
- [quickstart.md](quickstart.md)

## Post-Design Constitution Check

- **Reproducible Pipeline Runs**: PASS. Design records selector name/version,
  selector-affecting settings, input sparse references, coverage summaries, and
  warnings in patch metadata and run records.
- **Observable Long-Running Work**: PASS. Diagnostics and run records expose
  why cameras were selected, rejected, warned, or reused.
- **Explicit Resume And Overwrite Behaviour**: PASS. Contracts require
  incompatible selector signatures to be detected and decided before patching.
- **Modular, Testable Implementation**: PASS. Data model and tasks separate
  target sampling, projection, scoring, greedy selection, diagnostics, and
  reuse detection.
- **External Tool Validation**: PASS. No new executable is introduced; existing
  sparse text export and wildflow patching validation remain sufficient.
- **Data Safety**: PASS. Selector validation is read-only against SfM outputs
  and writes only derived patch artefacts under the active run directory.
