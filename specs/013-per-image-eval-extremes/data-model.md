# Data Model: Per-Image Evaluation Extremes

## AcceptedRun

- `dataset_id`, `dataset`
- `outer_run_id`, authoritative prefix
- selected attempt evidence and terminal state
- expected patch IDs, object counts and bytes

Validation: one accepted run family per dataset; ten unique accepted patches; cell is 1024/SIFT/global + 2048/200/2M.

## AcceptedPatch

- `probe_run_id`, `patch_id`, `attempt`
- final iteration and Gaussian count
- target image source
- manifest, holdout, eval sparse, metrics and status identities/checksums
- route: `backfill_from_saved_pairs` or `fallback_eval_only`

State: inventoried → downloaded → checksum-verified → mapped → scored → exported → visually accepted. Any failed validation moves to failed with a reason.

## ComparisonMapping

- `comparison_index`
- zero-based eval position
- POSIX relative `image_name`
- `test_every`
- eval-manifest checksum

Validation: numeric indices are contiguous; selected sparse positions equal the manifest holdout set and comparison count; names are unique.

## PerImageScore

Required fields are the schema in `contracts/per-image-csv.md`. Metric values derive from one decoded composite. Infinite PSNR is allowed only for identical halves; LPIPS and SSIM must be finite.

Uniqueness:

- `(dataset, patch_id, comparison_index)`
- `(dataset, patch_id, image_name)`

## ExtremeSelection

- score identity
- class (`best` or `worst`)
- rank
- GT/render/comparison paths and checksums

Validation: ascending LPIPS/name for best; descending LPIPS then ascending name for worst; no duplicate selection rows when fewer than six images.

## ProcessingManifest

- command/config and Git/container provenance
- input/output checksums and byte counts
- progress and terminal status
- aggregate reproduction and validation findings
