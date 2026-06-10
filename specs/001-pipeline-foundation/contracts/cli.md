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

## Step Selection

Future full-pipeline behaviour:
- `uv run main.py --config <config.yml>` runs all configured pipeline steps by
  default.
- `uv run main.py --config <config.yml> --steps <step>[,<step>...]` limits the
  invocation to the requested steps.

Feature 1 behaviour:
- Accept and record requested steps as part of the foundation CLI surface.
- Do not execute COLMAP, undistortion, patching, LFS training, cleanup,
  compression, or merge work.
- Treat selected steps as the scope for preflight resume/overwrite checks.

## Partial Run Decisions

Interactive runs:
- If a partial prior run is detected, prompt for resume/continue or start-over.
- If config values changed, show the diff before any stage runs and require an
  explicit continue-or-overwrite decision.
- If multiple requested steps need decisions, prompt for each affected step
  separately and complete every prompt before any step starts.

Non-interactive runs:
- Fail when a partial run requires a decision unless an explicit decision flag or
  policy is supplied.

Decision interface:
- `--resume-policy prompt`: default. Prompt in interactive runs; fail in
  non-interactive runs when a decision is required.
- `--resume-policy resume`: continue/resume prior generated outputs for every
  requested step that requires a decision.
- `--resume-policy overwrite`: start over/overwrite prior generated outputs for
  every requested step that requires a decision.
- `--resume-policy fail`: fail if any requested step has prior partial or
  completed outputs requiring a decision.

All resume-policy decisions must be recorded in `cli_overrides.json`,
`run_manifest.json`, and the run logs.

## Exit Behaviour

- `0`: foundation checks passed and run records were written.
- Non-zero: validation failed, a required decision was missing, or a required tool
  check failed.
