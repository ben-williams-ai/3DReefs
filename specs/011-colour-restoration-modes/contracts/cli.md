# CLI Contract: Colour Restoration Modes

## Pipeline Run

```bash
uv run main.py --config <config.yml> --steps <steps> [--resume-policy prompt|resume|overwrite|fail]
```

### Mode Behaviour

- `colour_restoration.mode: off`
  - Does not create or require colour state.
  - Does not open the GUI.
  - Does not write restored images.
  - SfM, COLMAP undistortion, and splatting use raw images.

- `colour_restoration.mode: gray_world`
  - Applies gray-world correction with strength `1.0` to every dataset image.
  - Writes a complete `recoloured_images/` tree before restored images are used by splatting-stage image inputs.
  - Records complete colour state for the run.
  - Does not open the GUI.
  - SfM and COLMAP undistortion still use raw images.

- `colour_restoration.mode: manual`
  - Preserves existing GUI/keyframe open, resume, apply, and completion behaviour.
  - `colour_restoration.start_sfm_immediately: true` allows raw-image SfM to run while the GUI is available.
  - SfM and COLMAP undistortion always use raw images.
  - Active or incomplete manual state blocks splat work that would consume colour-restored images.

### Overwrite Behaviour

- `colour_restoration.overwrite: false`
  - Reuses same-run restored images for splatting when state and output validation prove they are compatible.
  - Fails on incomplete, stale, cross-run, or cross-mode restored outputs.

- `colour_restoration.overwrite: true`
  - Regenerates same-run restored images for splatting/review through the explicit overwrite path.
  - Must not silently delete or replace unrelated user outputs.

## SfM And Undistortion Source Invariant

SfM feature extraction, matching, reconstruction, and COLMAP undistortion always use raw images for every colour restoration mode. Colour-restored images are never used as COLMAP inputs. Completed compatible restored images may only be selected later as splatting-stage image inputs or reviewed by the user.

## Colour Apply

```bash
uv run main.py colour apply --config <config.yml> --run-id <run_id>
```

- In `gray_world` mode, applies automatic gray-world restoration without opening the GUI.
- In `manual` mode, applies saved manual keyframe corrections.
- In `off` mode, exits clearly because there is no colour restoration work to apply.

## Colour Open

```bash
uv run main.py colour open --config <config.yml> --run-id <run_id>
```

- Meaningful only for `manual` mode.
- In `off` or `gray_world` mode, exits clearly with guidance to use `manual` if the GUI is desired.

## Error Cases

- Missing `colour_restoration` block: config validation error.
- Legacy `project.recolour_images`: config validation error naming the top-level block.
- Legacy `project.start_sfm_immediately`: config validation error naming the replacement field.
- Unsupported mode: config validation error listing `off`, `gray_world`, and `manual`.
- Incompatible restored outputs for splatting: fail with explicit overwrite/regeneration guidance.
