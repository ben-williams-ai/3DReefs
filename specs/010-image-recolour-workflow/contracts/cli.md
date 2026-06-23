# CLI Contract: Optional Image Recolour Workflow

This contract describes user-facing command behaviour. Exact Click function names may vary during implementation, but these behaviours must be available from the normal `uv run main.py ...` entrypoint.

## Pipeline Run With Colour Restoration

```bash
uv run main.py --config <config.yml> --steps sfm,splat --resume-policy <policy>
```

**Preconditions**:
- Config includes `project.recolour_images: true` to enable colour restoration.
- Config includes `project.start_sfm_immediately: true|false`; default is `true`.
- `raw_images/` exists and passes normal preflight.

**Behaviour**:
- Runs normal preflight before colour restoration.
- If `project.start_sfm_immediately` is true, raw-image SfM may run while the colour GUI is active.
- If false, SfM waits until colour restoration is complete or skipped.
- Splat stages wait while colour state is incomplete, active, applying, failed, or a GUI/session is active.
- SfM feature extraction, matching, reconstruction, and COLMAP undistortion always use raw images.
- Splatting uses raw images when colour restoration is skipped/disabled, or completed corrected images as splatting-stage image inputs when colour restoration is complete.

**Exit/failure conditions**:
- Fails early if the GUI cannot open when colour restoration is required.
- Fails before splatting if required corrected splatting images are missing, incomplete, or inconsistent.
- Continues as non-colour-restored only when the user explicitly skips colour restoration.

## Reopen Existing Colour GUI

```bash
uv run main.py colour open --config <config.yml> --run-id <run_id>
```

**Preconditions**:
- `<project.dir>/runs/<run_id>/colour_restoration/state.json` exists, or enough run/config data exists to initialise it.

**Behaviour**:
- Reopens the GUI with saved keyframes, parameters, mode, ordering, recent position where available, and output paths.
- Allows edits to completed or incomplete colour restoration state.
- Marks the colour session active while the GUI is open.
- Reapplying correction over existing outputs requires a warning that the current corrected version will be overwritten and explicit confirmation.

**Postconditions**:
- State records `complete`, `skipped`, `cancelled`, `failed`, or `incomplete`.
- Splatting remains blocked while the session is active.

## Standalone Colour Restoration

```bash
uv run main.py colour apply --config <config.yml> --run-id <run_id>
```

or:

```bash
uv run main.py colour open --config <config.yml> --run-id <run_id>
```

**Behaviour**:
- Performs keyframe selection, editing, state saving, resumption, and full-dataset correction without running SfM, patching, or splatting.
- Uses the same state file and corrected output folder as pipeline-driven colour restoration.
- Does not write or alter COLMAP undistortion outputs; COLMAP undistortion remains a raw-image pipeline step.

## Existing Main Pipeline With Colour Disabled

```bash
uv run main.py --config <config.yml> --steps sfm,splat --resume-policy <policy>
```

**Preconditions**:
- Config has `project.recolour_images: false` or omits it where the default applies.

**Behaviour**:
- Does not open colour GUI.
- Does not create or require `recoloured_images/`.
- Uses existing raw-image SfM and undistortion behaviour.
- Maintains current tests and output paths.

## User Prompts

When not all keyframes are edited, apply confirmation must include:

```text
You have not corrected N keyframes. Are you sure you want to finish and apply colour correction to all Y images in the dataset using the Q edited keyframes?
```

When all keyframes are edited, apply confirmation must include:

```text
Ready to colour correct all Y images, proceed?
```

When closing before completion, choices must include:

```text
Yes, and cancel job
Yes, progress to SfM without colour restoration
No, continue applying colour restoration
```

When reapplying over existing corrected outputs, prompt must warn that the current corrected version will be overwritten.
