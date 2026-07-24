# Per-Image CSV Contract

The canonical combined and per-dataset CSVs use this ordered minimum schema:

```text
dataset_id,dataset,outer_run_id,probe_run_id,patch_id,attempt,iteration,comparison_index,image_name,gt_width,gt_height,render_width,render_height,lpips,psnr,ssim,metric_source,target_image_source,source_comparison_path,source_comparison_sha256,eval_manifest_sha256,git_commit,container_digest,status,failure_reason
```

Rules:

- `image_name` is a POSIX relative path and may retain camera subdirectories.
- `iteration` is `30000` for accepted historical backfill.
- Metrics are decimal numbers; PSNR alone may be `inf` for identical images.
- Successful rows have `status=complete` and an empty `failure_reason`.
- Source paths are relative to `data/patch-results/`.
- Every successful row includes both source-comparison and eval-manifest SHA-256.
- Files are UTF-8 CSV with one header and atomic replacement.
- Future normal evaluation may write the identity/metric subset before run-level provenance is available; the historical backfill output must contain the full schema.
