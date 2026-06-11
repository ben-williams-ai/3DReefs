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

## 2026-06-10 - Stale Placeholder SfM Steps In Foundation Tests

- Branch: `002-colmap-sfm-pipeline`
- Error or symptom: Foundation tests started failing with image-dimension or COLMAP-stage errors.
- Context or command: `uv run pytest tests/unit tests/integration`
- Likely cause: Feature 1 tests used `--steps sfm` as an inert placeholder, but Feature 2 makes `sfm` a real COLMAP pipeline step.
- Fix or workaround: Use `--steps foundation` or another non-SfM placeholder in foundation-only tests; use dedicated SfM tests for `--steps sfm`.

## 2026-06-10 - Intrinsics Selection Without Actual Pre-Calculation

- Branch: `002-colmap-sfm-pipeline`
- Error or symptom: A smoke run completed, but the main feature extraction used only COLMAP's default focal prior instead of estimated camera parameters.
- Context or command: First local `uv run main.py --config configs/test.yml --steps sfm --resume-policy overwrite` smoke run.
- Likely cause: The implementation recorded selected calibration images but did not yet run a subset calibration stage.
- Fix or workaround: Add `sfm.intrinsics.*` stages that reconstruct a selected-image subset, export `cameras.txt`, and pass `--ImageReader.camera_params` into the full feature extraction.

## 2026-06-10 - Vocabulary Tree Required For Default SfM Matching

- Branch: `002-colmap-sfm-pipeline`
- Error or symptom: SfM preflight fails with `Selected SfM matching mode requires a valid tools.vocab_tree_path`.
- Context or command: `uv run main.py --config <config.yml> --steps sfm`
- Likely cause: The default matching mode runs sequential matching plus vocabulary-tree matching, and no valid vocabulary tree file is configured.
- Fix or workaround: Download a COLMAP-compatible vocabulary tree and set `tools.vocab_tree_path` in a local config, or choose a matching mode that does not use vocabulary-tree retrieval.
