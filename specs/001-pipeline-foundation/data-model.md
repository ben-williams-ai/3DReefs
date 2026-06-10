# Data Model: Pipeline Foundation

## PipelineConfig

Represents the source config after loading defaults but before CLI overrides.

Fields:
- `project.dir`: dataset/project directory. Required.
- `project.recolour_images`: whether recoloured images should be validated for
  later undistortion. Default `false`.
- `tools.colmap_bin`: COLMAP binary path or command. Advanced.
- `tools.lfs_bin`: LichtFeld Studio binary path or command. Advanced.
- `tools.splat_transform_bin`: SOG conversion command. Advanced, required only
  when SOG is enabled.
- `logging`: logging and run-record preferences.
- Future advanced sections may exist but are not executed in Feature 1.

Validation rules:
- Unknown keys fail unless explicitly allowed by the schema for future sections.
- Public example configs must use placeholders for private dataset paths.
- Config values must be serialisable to the effective config.

## ProjectDirectory

Represents the resolved dataset root.

Fields:
- `root`: resolved path from `project.dir` or `--project-dir`.
- `raw_images`: derived as `<root>/raw_images`.
- `recoloured_images`: derived as `<root>/recoloured_images`.
- `runs`: derived as `<root>/runs`.
- `camera_layout`: `single`, `multi`, or invalid.

Validation rules:
- `raw_images` must exist.
- Direct images under `raw_images` imply `single`.
- Camera subfolders under `raw_images` imply `multi`.
- Mixing direct images and camera subfolders is invalid.
- If recolouring is enabled, `recoloured_images` must mirror relative paths and
  filenames from `raw_images`.

## CliOverride

Represents one command-line override.

Fields:
- `key`: dotted config path, such as `splat.train.num_iters`.
- `raw_value`: original CLI string.
- `parsed_value`: value after type coercion.
- `source`: `cli`.

Validation rules:
- Key must map to a known schema path.
- Parsed value must satisfy the target field type and constraints.
- Unknown or invalid overrides fail before run outputs are created.

## EffectiveConfig

Represents the actual settings used for a run after defaults, config file values,
and CLI overrides are applied.

Fields:
- All accepted config fields.
- Derived paths.
- Applied CLI overrides.
- Tool paths selected for validation.

Validation rules:
- Must be written for every successful foundation run.
- Must be comparable with a previous run's effective config.
- Must not contain secrets.

## RunRecord

Represents a self-contained run attempt.

Fields:
- `run_id`: stable identifier for the run directory.
- `source_config_path`: path to the config file used.
- `effective_config_path`: path to stored effective config.
- `cli_overrides_path`: path to stored override record.
- `run_manifest_path`: path to manifest.
- `run_status_path`: path to status.
- `timings_path`: path to timing records.
- `logs_dir`: directory for logs.
- `reports_dir`: directory for reports.
- `tool_validation_results`: validation outcomes.
- `resume_events`: list of resume/start-over decisions.
- `config_diff_events`: list of config differences detected against previous runs.

State transitions:
- `created` -> `preflight_running` -> `preflight_passed`
- `created` -> `preflight_failed`
- `preflight_passed` -> `complete` for foundation-only runs
- `partial_detected` -> `resume_confirmed` or `overwrite_confirmed`
- `partial_detected` -> `failed_non_interactive_decision_required`

## PartialRun

Represents a prior run that did not finish the requested workflow or has generated
outputs that may affect the next invocation.

Fields:
- `run_dir`
- `status`
- `last_completed_stage`
- `effective_config`
- `manifest`
- `logs`

Validation rules:
- Missing or corrupt status is treated as a partial/uncertain run and requires
  explicit user attention.
- Config differences are computed before any new stage runs.

## ToolValidationResult

Represents the outcome of validating an external tool.

Fields:
- `tool_name`
- `configured_path`
- `detected_version`
- `target_version`
- `capabilities_checked`
- `status`: `passed`, `failed`, or `skipped`
- `message`
- `duration_seconds`

Validation rules:
- COLMAP and LFS are always checked in Feature 1.
- SOG conversion is checked only when SOG is enabled.
- Failed required tool checks fail the foundation run before heavy work.
