# Quickstart: Splat Cleanup And SOG Compression

This feature assumes a Feature 3 run has already produced trained patch splats.

## 1. Validate Tooling

Ensure the local config provides:

- `wildflow` installed with `splat.cleanup_splats` and `splat.merge_ply_files`
- `splat-transform` compatible with the project-required version

Public example configs should use placeholders or environment variable references, not private absolute paths.

## 2. Run Full Post-Processing

```bash
uv run main.py \
  --config configs/test.yml \
  --run-id <RUN_ID> \
  --steps splat.postprocess
```

Expected outputs:

```text
<project.dir>/runs/<RUN_ID>/splat/postprocess/postprocess_manifest.json
<project.dir>/runs/<RUN_ID>/splat/merged/merged_splat.ply
<project.dir>/runs/<RUN_ID>/splat/sog/merged_splat.sog
```

## 3. Run Individual Stages

Cleanup only:

```bash
uv run main.py \
  --config configs/test.yml \
  --run-id <RUN_ID> \
  --steps splat.cleanup
```

Merge only:

```bash
uv run main.py \
  --config configs/test.yml \
  --run-id <RUN_ID> \
  --steps splat.merge
```

SOG only:

```bash
uv run main.py \
  --config configs/test.yml \
  --run-id <RUN_ID> \
  --steps splat.sog
```

## 4. Rerun Safely

To overwrite generated post-processing outputs without an interactive prompt:

```bash
uv run main.py \
  --config configs/test.yml \
  --run-id <RUN_ID> \
  --steps splat.postprocess \
  --resume-policy overwrite
```

The pipeline must resolve all reuse/overwrite/fail decisions before any cleanup, merge, or SOG operation starts.

## 5. Verify Results

Check:

- `run_status.json` reports completed post-processing only after cleanup, merge, and requested SOG complete or are reused.
- `splat/postprocess/postprocess_manifest.json` lists every patch as included, excluded, cleaned, failed, skipped, or reused.
- `splat/merged/merged_splat.ply` exists after merge.
- `splat/sog/merged_splat.sog` exists after successful SOG export.
- warnings identify incomplete patch sources and excluded patches.
