# CLI Contract: Splat Cleanup And SOG Compression

## Supported Steps

Post-processing adds these explicit step names:

- `splat.cleanup`: select trained patch sources and create cleaned patch PLYs.
- `splat.merge`: merge cleaned patch PLYs into one site-level cleaned PLY.
- `splat.sog`: export one final SOG from the merged cleaned PLY.
- `splat.postprocess`: run cleanup, merge, then SOG according to config.

The existing Feature 3 `splat` behaviour is not redefined by this feature.

## Example Commands

Run full post-processing for an existing run:

```bash
uv run main.py \
  --config configs/test.yml \
  --run-id <RUN_ID> \
  --steps splat.postprocess
```

Run cleanup only:

```bash
uv run main.py \
  --config configs/test.yml \
  --run-id <RUN_ID> \
  --steps splat.cleanup
```

Run merge and SOG after cleanup already exists:

```bash
uv run main.py \
  --config configs/test.yml \
  --run-id <RUN_ID> \
  --steps splat.merge,splat.sog
```

Overwrite existing post-processing outputs non-interactively:

```bash
uv run main.py \
  --config configs/test.yml \
  --run-id <RUN_ID> \
  --steps splat.postprocess \
  --resume-policy overwrite
```

## Preflight Behaviour

Before any requested post-processing operation starts, the CLI must:

- Resolve the run directory from `project.dir`, `advanced.paths.runs_dir`, and `--run-id`.
- Validate Feature 3 training outputs needed by the requested steps.
- Validate wildflow cleanup support when cleanup is requested.
- Validate wildflow cleaned PLY merge support when merge is requested.
- Validate `splat-transform` when SOG is requested, or when SOG is enabled in the requested workflow.
- Detect existing cleaned patch outputs, merged PLY, and final SOG outputs.
- Resolve reuse, overwrite, or fail decisions for every conflict.
- Warn if relevant post-processing settings changed from the previous partial run.

Interactive prompts are allowed only during this preflight phase. Non-interactive runs must fail before work starts if a decision is required and not provided.

## Exit Status

- Exit `0` when all requested post-processing steps complete or are reused according to explicit decisions.
- Exit non-zero when a requested cleanup or wildflow merge step fails before a valid merged cleaned PLY is available.
- If SOG export fails after a valid merged cleaned PLY exists, preserve the merged PLY, mark post-processing as partial, emit prominent warnings, and keep the partial result resumable.

## Public Path Safety

CLI logs and summaries may show paths relative to the run directory. Public docs and example configs must not include private absolute dataset paths.
