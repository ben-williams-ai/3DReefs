# Troubleshooting

## 2026-06-10 - Invalid Config

- Branch: `001-pipeline-foundation`
- Error or symptom: The CLI exits before creating a run directory.
- Context or command: `uv run main.py --config <config.yml>`
- Likely cause: Missing required config keys, malformed YAML, wrong value types, or unknown dotted CLI overrides.
- Fix or workaround: Validate the config against `configs/example.yml`; correct unknown override keys before rerunning.

## 2026-06-10 - Ambiguous Image Layout

- Branch: `001-pipeline-foundation`
- Error or symptom: `raw_images mixes direct images and camera subfolders`.
- Context or command: Foundation preflight during image layout validation.
- Likely cause: `raw_images/` contains both direct image files and camera folders.
- Fix or workaround: For single-camera data, place images directly in `raw_images/`. For multi-camera data, place images inside `raw_images/cam1/`, `raw_images/cam2/`, and so on.

## 2026-06-10 - Missing External Tool

- Branch: `001-pipeline-foundation`
- Error or symptom: Tool validation fails for COLMAP, LichtFeld Studio, or `splat-transform`.
- Context or command: Foundation preflight validates only bounded version/help commands.
- Likely cause: The configured binary is not on `PATH`, points to the wrong executable, or reports an unsupported version.
- Fix or workaround: Update the local config `tools.*_bin` value or install the expected tool version.

## 2026-06-10 - Partial-Run Conflict

- Branch: `001-pipeline-foundation`
- Error or symptom: Non-interactive runs fail with a required resume/overwrite decision.
- Context or command: Re-running a project with prior partial outputs.
- Likely cause: The pipeline found uncertain prior outputs and cannot safely continue without explicit intent.
- Fix or workaround: Run interactively, or pass `--resume-policy resume`, `--resume-policy overwrite`, or `--resume-policy fail`.
