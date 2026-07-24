# Implementation Plan: Per-Image Evaluation Extremes

**Branch**: `feature/per-image-eval-extremes` | **Date**: 2026-07-24 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/013-per-image-eval-extremes/spec.md`

## Summary

Extend the existing Python-owned image-metric path to retain per-image rows, then add one thin backfill/export CLI that maps LFS comparison indices through the reordered eval sparse model and `test_every`. Reuse saved accepted final-step composites, existing metric functions and installed dependencies; preserve aggregate outputs and raw inputs.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: Pillow, NumPy, scikit-image, PyTorch, LPIPS (all existing)
**Storage**: Local files, CSV/JSON manifests and S3-compatible object storage via existing tooling
**Testing**: pytest as configured in `pyproject.toml`, plus Python compilation and `git diff --check`
**Target Platform**: Ubuntu Linux with NVIDIA CUDA GPU
**Project Type**: Importable Python package plus thin CLI/script
**Performance Goals**: Score the verified 898-image preliminary inventory sequentially/resumably without re-downloading verified objects
**Constraints**: No new dependency; 40+ GB raw inputs; raw files immutable; exact scientific metric compatibility; no training/SfM rerun by default
**Scale/Scope**: Six datasets, sixty accepted patches, approximately 898 full-resolution comparison images

## Constitution Check

- **I Reproducible runs — PASS**: score/export manifests record inputs, parameters, software identity and checksums.
- **II Observable long-running work — PASS**: CLI emits patch/image progress and writes atomic resumable outputs.
- **III Explicit resume/overwrite — PASS**: existing output is validated and resumed; conflicting output fails unless separately archived.
- **IV Modular/testable — PASS**: shared metric/mapping logic lives under `src/`; wrapper remains thin; focused tests cover contracts.
- **V External tool validation — PASS**: GPU/LPIPS and object-store access are checked before heavy work; no silent metric fallback.
- **VI Data safety — PASS**: raw comparisons are read-only, generated outputs are separate and the complete data tree is ignored.

Post-design re-check: PASS. No constitution exception or complexity justification is required.

## Project Structure

### Documentation (this feature)

```text
specs/013-per-image-eval-extremes/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── per-image-csv.md
└── tasks.md
```

### Source Code

```text
src/reefs/eval/
├── image_metrics.py        # canonical per-image calculation and aggregate means
├── lpips.py                # existing composite split and LPIPS implementation
└── per_image_backfill.py   # mapping, validation, ranking and export

scripts/
└── backfill_per_image_eval.py  # thin command wrapper

tests/
├── unit/
│   ├── test_eval_image_metrics.py
│   └── test_per_image_backfill.py
└── integration/
    └── test_per_image_backfill.py
```

**Structure Decision**: Add one focused module beside the existing evaluation implementation and one thin operational wrapper. Do not introduce a new package, framework or dependency.

## Design

1. Parse COLMAP text `eval_sparse/images.txt` in file order.
2. Select records whose zero-based position is divisible by manifest `test_every`.
3. Require the selected names to equal the manifest holdout set and comparison count; map sorted numeric comparison indices to those selected records in order.
4. Split each composite with the existing four-pixel splitter, compute all three metrics in one pass and write canonical per-image rows atomically.
5. Derive legacy aggregate means from those same rows so future evaluation cannot drift.
6. Backfill enriches canonical metric rows with run provenance, validates accepted metadata and exports deterministic extremes without altering raw files.

## Verification

- Synthetic metric, malformed composite, mapping and deterministic-ranking unit tests.
- Integration test for per-dataset/combined CSV and split exports.
- Existing evaluation and Stage 2 probe tests.
- Python compilation and `git diff --check` (the repository has no configured formatter, linter or type checker).
- One real downloaded canary patch, checksum verification and visual inspection before the full transfer.
- Full inventory/count/uniqueness/aggregate reproduction checks and visual inspection across all datasets.

## Complexity Tracking

No violations.
