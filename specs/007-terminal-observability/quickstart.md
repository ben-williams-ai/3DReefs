# Quickstart: Live Terminal Output

Run a short mocked or existing splat command:

```bash
uv run main.py \
  --config configs/datasets/dataset_01.yml \
  --run-id trial_dataset1_patch400_p000-p002 \
  --steps splat.patch,splat.train,splat.cleanup,splat.merge \
  --resume-policy overwrite \
  --advanced.splat.patching.max_cameras 400 \
  --advanced.splat.train.patch_ids "[p000,p001,p002]" \
  --advanced.splat.cleanup.patch_ids "[p000,p001,p002]" \
  --advanced.splat.merge.patch_ids "[p000,p001,p002]" \
  --advanced.splat.train.num_splats_per_patch 1000000
```

Expected terminal behaviour:

- The command prints preflight and validation stages immediately.
- Outlier filtering and patch generation print coarse progress before LFS starts.
- LFS training output appears live while still being saved to logs.
- Cleanup and merge print per-stage completion.
