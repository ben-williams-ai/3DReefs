# Research: Per-Image Evaluation Extremes

## Decision: Backfill authoritative saved composites

**Rationale**: Final 30,000-iteration GT/render composites exist for the selected cell. Recomputing metrics from them preserves the evaluated pixels and avoids scientifically unnecessary retraining or rendering.

**Alternatives considered**: Retraining (rejected); evaluation-only rerun (conditional fallback only); historical aggregate CSV substitution (cannot recover image-level scores).

## Decision: Reuse the canonical Python metric path

**Rationale**: `reefs.eval.image_metrics` already owns PSNR/SSIM and `reefs.eval.lpips` owns AlexNet LPIPS with the required normalisation and four-pixel split.

**Alternatives considered**: Separate offline metric stack (drift risk); new dependency (forbidden and unnecessary).

## Decision: Prove identity from eval sparse order

**Rationale**: `build_eval_dataset()` rewrites sparse image order so LFS `--test-every` positions contain holdouts. Therefore comparison index identity must be reconstructed from the persisted reordered `images.txt` plus manifest `test_every`, then checked against `holdout_images`.

**Alternatives considered**: Manifest list position (unproven); lexical image order (incorrect); numeric comparison index matched directly to source IDs (not guaranteed).

## Decision: One canonical per-image computation feeds aggregates

**Rationale**: Computing each metric once and averaging those rows is the smallest way to guarantee per-image and legacy aggregate consistency.

**Alternatives considered**: Retain separate aggregate loops (duplicate work and drift); change public return contracts (unnecessary).

## Decision: CSV/JSON and atomic replacement

**Rationale**: Existing repository ledgers already use CSV/JSON and atomic replacement. This keeps outputs inspectable, resumable and dependency-free.

**Alternatives considered**: SQLite/Parquet (new complexity/dependencies); in-memory-only full run (not resumable).

## Decision: Sequential GPU scoring first

**Rationale**: The inventory is under one thousand large images; sequential scoring minimises VRAM risk and preserves clear patch progress. Optimised batching is unnecessary unless measured runtime demands it.

**Alternatives considered**: Dataset-wide batching (more memory and recovery complexity); six VMs (unnecessary).
