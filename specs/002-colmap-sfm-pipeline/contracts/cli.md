# CLI Contract: COLMAP SfM Pipeline

## Run SfM Stages

```bash
uv run main.py --config <config.yml> --steps sfm
```

Behaviour:
- Runs foundation preflight plus SfM preflight.
- Runs intrinsics handling, feature extraction, matching, reconstruction, and
  undistortion.
- Runs dense/mesh only when explicitly enabled.
- Does not run splat outlier filtering, patching, LFS training, cleanup, SOG, or
  merge stages.

## Run Selected SfM Substages

```bash
uv run main.py --config <config.yml> --steps sfm.match,sfm.reconstruct
```

Supported step names for this feature:
- `sfm`
- `sfm.preflight`
- `sfm.intrinsics`
- `sfm.extract`
- `sfm.match`
- `sfm.reconstruct`
- `sfm.undistort`
- `sfm.dense`
- `sfm.mesh`

All requested steps are inspected for prior outputs before any step starts.

## Config Overrides

```bash
uv run main.py --config <config.yml> --advanced.sfm.reconstruction.backend incremental
uv run main.py --config <config.yml> --advanced.sfm.dense.enabled true
uv run main.py --config <config.yml> --advanced.sfm.feature_extraction.max_num_features 4096
```

Behaviour:
- Unknown override keys fail before heavy work.
- Accepted overrides are recorded in `cli_overrides.json`.
- Effective values are written to `effective_config.yml`.

## Mixed Camera Source Decision

Interactive runs:
- If metadata suggests mixed camera sources in a camera group, prompt before any
  SfM step starts.
- Continue only after explicit confirmation.

Non-interactive runs:
- Fail unless the effective config contains an explicit pre-supplied proceed
  setting.

## Resume And Overwrite

Existing `--resume-policy` applies to SfM stages:
- `prompt`: ask interactively, fail in non-interactive contexts when a decision is
  required.
- `resume`: reuse/resume prior outputs where valid.
- `overwrite`: rerun/overwrite prior outputs.
- `fail`: fail if any requested stage has prior outputs requiring a decision.

All stage decisions must be complete before execution starts and must be recorded
in the run manifest/logs.

## Exit Behaviour

- `0`: requested SfM stages completed or were validly reused.
- Non-zero: validation failed, required resource missing, required decision
  missing, selected backend unavailable, COLMAP command failed, or required
  output could not be selected.
