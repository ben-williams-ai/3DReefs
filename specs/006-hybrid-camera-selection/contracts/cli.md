# CLI Contract: Hybrid Camera Selection

## Run Patch Generation With The Hybrid Selector

```bash
uv run main.py --config <config.yml> --steps splat.patch
```

Behaviour:
- Uses existing Feature 3 patch-bound generation.
- Uses the Target-Aware Spatial Greedy selector as the only camera selector.
- Does not expose or accept a selector-mode switch.
- Writes selected patch datasets and diagnostics under the active run directory.
- Does not launch LFS training unless `splat.train` is also requested.

## Regenerate Existing Patches

```bash
uv run main.py \
  --config <config.yml> \
  --run-id <run_id> \
  --steps splat.patch \
  --resume-policy overwrite
```

Behaviour:
- Detects existing patch outputs before patch work begins.
- If selector-affecting settings or selector version changed, resolves reuse or
  overwrite up front.
- Writes warnings and overwrite/reuse decisions to the existing run record.

## Diagnostic-Only Validation

There is no separate selector mode. Diagnostic validation uses normal patch
generation and then inspects the outputs:

```text
<project.dir>/runs/<run_id>/splat/patches/<patch_id>/patch_metadata.json
<project.dir>/runs/<run_id>/splat/patches/<patch_id>/patch_diagnostics/
```

Exit behaviour:
- `0`: requested patch generation completed, reused valid outputs, or completed
  with warning-only selector coverage issues.
- Non-zero: source sparse files are missing or invalid, patch metadata is
  malformed, selected images cannot be staged, sparse export fails, or a required
  up-front reuse/overwrite decision is missing.
