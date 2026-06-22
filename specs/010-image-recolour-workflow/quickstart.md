# Quickstart: Optional Image Recolour Workflow

This quickstart uses placeholders. Replace config paths, project directories, and run ids with local values.

## 1. Update Configuration

Enable colour restoration in a project config:

```yaml
project:
  dir: /path/to/project
  recolour_images: true
  start_sfm_immediately: true
```

For default existing behaviour:

```yaml
project:
  recolour_images: false
```

## 2. Run The Pipeline With Colour Restoration

```bash
uv run main.py \
  --config configs/example.yml \
  --steps sfm,splat \
  --resume-policy overwrite
```

Expected behaviour:

- Preflight validates raw image layout and tools.
- SfM geometry runs on `raw_images/`.
- In an interactive terminal, the colour GUI opens when colour restoration is enabled.
- If `project.start_sfm_immediately` is true, the GUI is opened in the background so raw-image SfM can continue.
- If `project.start_sfm_immediately` is false, SfM waits until colour restoration is complete or skipped.
- Corrected full-resolution images are written to `recoloured_images/`.
- Final downstream handoff remains `runs/<run_id>/sfm/undistorted/images` and `runs/<run_id>/sfm/undistorted/sparse`.
- Splatting waits while colour restoration is active or incomplete.

## 3. Review Corrected Images

Inspect:

```text
<project.dir>/recoloured_images/
```

The folder should mirror `raw_images/` exactly by relative path and filename.

## 4. Reopen The Colour GUI For More Edits

```bash
uv run main.py colour open \
  --config configs/example.yml \
  --run-id <run_id>
```

Expected behaviour:

- Previous keyframes and saved edits are restored.
- The colour session is marked active while the GUI is open.
- Reapplying correction warns that the current corrected version will be overwritten.
- Splatting waits until the session is complete, skipped, cancelled, or closed safely.

## 5. Run Colour Restoration Standalone

```bash
uv run main.py colour open \
  --config configs/example.yml \
  --run-id <run_id>

uv run main.py colour apply \
  --config configs/example.yml \
  --run-id <run_id>
```

Use this when you want to tune and apply colour correction without running SfM, patching, or splatting in the same invocation.
If `recoloured_images/` already exists, confirm replacement explicitly:

```bash
uv run main.py colour apply \
  --config configs/example.yml \
  --run-id <run_id> \
  --overwrite
```

## 6. Resume After Failure

If a pipeline stage fails while the GUI is open, rerun with the same run id:

```bash
uv run main.py \
  --config configs/example.yml \
  --run-id <run_id> \
  --steps sfm,splat \
  --resume-policy resume
```

The colour state should be loaded from:

```text
<project.dir>/runs/<run_id>/colour_restoration/state.json
```

## 7. Focused Verification Commands

Run unit tests for colour logic:

```bash
uv run pytest tests/unit/test_colour_ordering.py tests/unit/test_colour_interpolation.py tests/unit/test_colour_state.py
```

Run integration tests for pipeline handoff and waiting behaviour:

```bash
uv run pytest tests/integration/test_colour_cli.py tests/integration/test_splat_colour_wait.py tests/integration/test_sfm_recoloured_undistortion.py
```

## 8. GUI Smoke Verification

The implemented GUI was smoke-checked in an offscreen Qt session with:

```bash
PYTHONPATH=src QT_QPA_PLATFORM=offscreen uv run python - <<'PY'
from pathlib import Path
from PIL import Image
from reefs.colour.gui import launch_colour_gui
from reefs.colour.pipeline import initialise_state, colour_state_path
from reefs.colour.interpolation import rebuild_keyframes
from reefs.colour.ordering import build_image_sequence
from reefs.colour.state import save_state
from dataclasses import replace

root = Path('/tmp/reefs-colour-gui-smoke')
raw = root / 'project' / 'raw_images'
run_dir = root / 'project' / 'runs' / 'gui-smoke'
raw.mkdir(parents=True, exist_ok=True)
run_dir.mkdir(parents=True, exist_ok=True)
Image.new('RGB', (32, 24), color=(20, 40, 60)).save(raw / 'img1.jpg')
state = initialise_state(run_id='gui-smoke', run_dir=run_dir, raw_images=raw, recoloured_images=root / 'project' / 'recoloured_images')
state = replace(state, keyframes=rebuild_keyframes(build_image_sequence(raw), count=1))
save_state(colour_state_path(run_dir), state)
code = launch_colour_gui(state=state, run_dir=run_dir, auto_close_ms=50)
print(f'gui_exit={code}')
PY
```

Result recorded during implementation: `gui_exit=0`.

The GUI was also opened on a tiny two-camera scratch dataset and captured at the
minimum supported size, 920x600:

```text
scratch/colour_gui_visual_check/gui_minimum_window_920x600.png
```

Visual inspection result: raw and corrected previews rendered, the parameter
controls remained usable with scrolling, keyframe rows showed raw thumbnails,
camera folder, dataset position, per-camera position, filename/path, saved
values, and row delete controls, and no controls overlapped at 920x600.
