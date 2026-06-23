# Quickstart: Colour Restoration Modes

## Example Config Block

```yaml
colour_restoration:
  # Default: off. Use off for raw images, gray_world for automatic correction,
  # or manual for the GUI/keyframe workflow.
  mode: off
  # Default: false. Reuse existing same-run restored images when false;
  # regenerate them through the explicit overwrite path when true.
  overwrite: false
  # Default: true. Manual mode may start raw-image SfM in the background while
  # the colour restoration GUI is available for editing.
  start_sfm_immediately: true
```

## Validate Config Migration

```bash
uv run pytest tests/unit/test_config_loader.py tests/unit/test_config_models.py
```

Expected:

- Valid `off`, `gray_world`, and `manual` modes load.
- Missing `colour_restoration.mode` defaults to `off`.
- Missing top-level `colour_restoration` block fails.
- Legacy `project.recolour_images` and `project.start_sfm_immediately` fail clearly.
- `configs/example.yml`, `configs/test.yml`, and dataset configs load.

## Run Off Mode

```bash
uv run main.py --config configs/example.yml --steps sfm.preflight
```

Expected:

- No colour state is created.
- No GUI opens.
- No restored image tree is created for this run.
- Raw images are used for SfM, COLMAP undistortion, and splatting inputs.

## Run Gray-World Mode

Set:

```yaml
colour_restoration:
  mode: gray_world
  overwrite: false
  start_sfm_immediately: true
```

Then run:

```bash
uv run main.py --config configs/example.yml --steps sfm
```

Expected:

- Full-resolution restored images are written under `recoloured_images/`.
- Output count and dimensions match raw images.
- Colour state records complete automatic restoration.
- GUI does not open.
- SfM and COLMAP undistortion still use raw images.
- Splatting-stage image inputs use the completed restored images.

## Run Manual Mode

Set:

```yaml
colour_restoration:
  mode: manual
  overwrite: false
  start_sfm_immediately: true
```

Then run:

```bash
uv run main.py --config configs/example.yml --steps sfm
uv run main.py colour open --config configs/example.yml --run-id <run_id>
uv run main.py colour apply --config configs/example.yml --run-id <run_id>
```

Expected:

- `colour open` opens or resumes the GUI.
- `colour apply` writes full-resolution manual outputs.
- Active/incomplete manual state blocks dependent splat work.
- Completed manual outputs may be reused when `overwrite: false`.
- SfM and COLMAP undistortion always use raw images; manual outputs are only for splatting-stage image inputs and review.

## Regression Suite

```bash
uv run pytest tests
```
