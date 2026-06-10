# CLI Contract: Pipeline Foundation

## Primary Command

```bash
uv run main.py --config <config.yml>
```

Behaviour:
- Loads the config file.
- Resolves `project.dir`.
- Derives standard project paths.
- Applies CLI overrides.
- Creates a run directory and run records.
- Performs foundation preflight checks only.
- Does not run COLMAP reconstruction, matching, undistortion, patching, LFS
  training, cleanup, compression, or merge.

## Optional Project Directory Override

```bash
uv run main.py --config <config.yml> --project-dir <dataset-root>
```

Behaviour:
- Overrides `project.dir` for this invocation.
- Records the override in `cli_overrides.json` and `run_manifest.json`.

## Dotted Config Overrides

```bash
uv run main.py --config <config.yml> --splat.train.num_iters 20000
```

Behaviour:
- Parses dotted flags as config path overrides.
- Fails before output creation when a key is unknown or the value fails validation.
- Stores accepted overrides separately from the effective config.

## Partial Run Decisions

Interactive runs:
- If a partial prior run is detected, prompt for resume/continue or start-over.
- If config values changed, show the diff before any stage runs and require an
  explicit continue-or-overwrite decision.

Non-interactive runs:
- Fail when a partial run requires a decision unless an explicit decision flag is
  supplied.

Decision flags are named during implementation planning/tasks, but must cover:
- continue/resume existing generated outputs.
- start over/overwrite generated outputs.

## Exit Behaviour

- `0`: foundation checks passed and run records were written.
- Non-zero: validation failed, a required decision was missing, or a required tool
  check failed.
