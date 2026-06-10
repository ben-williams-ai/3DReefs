# Run Record Contract: Pipeline Foundation

Every foundation run writes records under:

```text
<project.dir>/runs/<run_id>/
```

## Required Files

```text
effective_config.yml
cli_overrides.json
run_manifest.json
run_status.json
timings.json
logs/
  pipeline.log
  warnings.log
reports/
  preflight_report.md
```

Future stage logs such as `colmap.log` and `lfs.log` may be created by later
features, but Feature 1 only creates foundation/preflight records.

## `cli_overrides.json`

Required fields:
- `overrides`: list of `{key, raw_value, parsed_value, source}`.
- `project_dir_override`: value supplied through `--project-dir`, if any.

## `run_manifest.json`

Required fields:
- `run_id`
- `created_at`
- `source_config_path`
- `project_dir`
- `effective_config_path`
- `cli_overrides_path`
- `tool_versions`
- `resume_events`
- `config_diff_events`

## `run_status.json`

Required fields:
- `status`
- `current_stage`
- `last_completed_stage`
- `started_at`
- `ended_at`
- `warnings_count`
- `errors`

## `timings.json`

Required fields:
- `stages`: list of `{name, started_at, ended_at, duration_seconds, status}`.

Feature 1 timing stages include:
- `load_config`
- `apply_overrides`
- `derive_paths`
- `validate_inputs`
- `validate_tools`
- `detect_partial_runs`
- `write_run_records`

## Config Diff Event

When a previous partial run differs from the requested effective config, record:
- `previous_run_id`
- `detected_at`
- `differences`: list of `{path, previous_value, requested_value, source}`
- `decision`: `continue`, `overwrite`, or `blocked`
- `interactive`: boolean
