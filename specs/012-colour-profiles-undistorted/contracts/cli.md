# CLI Contract

```bash
uv run main.py colour profile create --config <config.yml> --output <profile.json>
```

Opens the current GUI, saves dataset-specific keyframes atomically, and requires no SfM run.

```bash
uv run main.py --config <config.yml> --run-id <run> --steps splat
```

With `mode: profile`, validates and applies the configured profile to the consumed undistorted training workspace without opening a GUI. Evaluation lazily prepares the corresponding full-resolution corrected target. With `mode: off`, neither action occurs.
