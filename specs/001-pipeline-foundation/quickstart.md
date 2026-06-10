# Quickstart: Pipeline Foundation

This quickstart verifies Feature 1 only. It must not run COLMAP reconstruction,
matching, undistortion, patching, LichtFeld Studio training, cleanup, compression,
or merge.

## 1. Install Project Environment

```bash
uv sync
```

## 2. Prepare A Minimal Dataset Directory

```bash
mkdir -p /tmp/3dreefs_foundation_demo/raw_images
touch /tmp/3dreefs_foundation_demo/raw_images/image_0001.jpg
```

Real tests should use small valid image files, but this sketch shows the required
layout.

## 3. Create A Local Config From The Example

```bash
cp configs/example.yml /tmp/3dreefs_foundation_demo/config.yml
```

Edit the copied config so:

```yaml
project:
  dir: /tmp/3dreefs_foundation_demo
  recolour_images: false
```

## 4. Run Foundation Check

```bash
uv run main.py --config /tmp/3dreefs_foundation_demo/config.yml
```

Expected result:
- config validates.
- `raw_images/` is detected.
- external tool version checks are attempted.
- because SOG is enabled by default in the example config, `splat-transform` is
  checked unless `splat.sog.enabled: false` is set in a local copy.
- a run directory is created under `/tmp/3dreefs_foundation_demo/runs/`.
- no heavy COLMAP or LFS stage starts.

## 5. Verify Run Records

Check the newest run directory contains:

```text
effective_config.yml
cli_overrides.json
run_manifest.json
run_status.json
timings.json
logs/pipeline.log
logs/warnings.log
reports/preflight_report.md
```

## 6. Verify CLI Override Recording

```bash
uv run main.py \
  --config /tmp/3dreefs_foundation_demo/config.yml \
  --project-dir /tmp/3dreefs_foundation_demo \
  --splat.train.num_iters 20000
```

Expected result:
- accepted overrides are present in `cli_overrides.json`.
- the effective config reflects the override.

## 7. Verify Partial Run Safety

Create or keep a partial run record, then re-run with changed config values.

Expected result:
- the change is detected during preflight.
- the diff is shown before any stage runs.
- interactive runs require a continue-or-overwrite decision.
- non-interactive runs fail unless the decision was supplied explicitly.
