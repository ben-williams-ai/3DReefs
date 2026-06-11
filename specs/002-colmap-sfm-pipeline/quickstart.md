# Quickstart: COLMAP SfM Pipeline

This quickstart verifies Feature 2 only. It may run COLMAP SfM stages when the
local config points at real tools and data. It must not run splatting, patching,
LFS training, cleanup, SOG compression, merge, NanoGS, LOD, or PlayCanvas work.

## 1. Prepare Environment

```bash
uv sync
uv run pytest tests/unit tests/integration
```

Confirm external tools/resources in your local config:

```bash
colmap -h
splat-transform --version
```

The default matching strategy requires a local vocabulary tree file configured
through `tools.vocab_tree_path`.

## 2. Prepare Data

Single camera:

```text
<project.dir>/
  raw_images/
    image_0001.jpg
```

Multi-camera:

```text
<project.dir>/
  raw_images/
    cam1/
    cam2/
```

Optional recoloured images:

```text
<project.dir>/
  recoloured_images/
    cam1/
    cam2/
```

Recoloured images must mirror raw relative paths, filenames, and dimensions.

## 3. Run SfM With Local Config

```bash
uv run main.py --config configs/test.yml --steps sfm --resume-policy overwrite
```

Expected:
- raw images are used for feature extraction, matching, and sparse reconstruction.
- undistortion uses raw images unless `project.recolour_images=true`.
- no splatting stages start.
- `logs/colmap.log` is written.

## 4. Run Only Selected SfM Steps

```bash
uv run main.py --config configs/test.yml --steps sfm.match,sfm.reconstruct --resume-policy resume
```

Expected:
- all prior-output decisions are resolved before the first requested step starts.
- selected steps reuse earlier valid prerequisites or fail clearly if missing.

## 5. Verify Outputs

Inspect newest run:

```text
<project.dir>/runs/<run_id>/
  effective_config.yml
  cli_overrides.json
  run_manifest.json
  run_status.json
  timings.json
  logs/pipeline.log
  logs/colmap.log
  sfm/
```

Check:
- `run_manifest.json` records selected sparse model counts.
- `timings.json` includes each SfM stage that ran.
- `sfm/undistorted/images` and `sfm/undistorted/sparse` exist after a successful
  full SfM run.

## 6. Verify Failure Cases

Use small fixtures or local temporary copies to check:
- missing vocabulary tree fails before matching.
- recoloured mirror mismatch fails before heavy SfM work.
- mixed camera-source metadata prompts interactively or fails non-interactively
  unless an explicit proceed setting is supplied.
- mesh enabled without dense enabled fails during preflight.
