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
```

Future stage logs such as `colmap.log` and `lfs.log` may be created by later
features, but Feature 1 only creates foundation/preflight records.

`logs/warnings.log` is optional and MUST be created only when warnings occur.
Feature 1 MUST NOT create `reports/preflight_report.md`; the manifest, status,
timings, config snapshot, override record, and process log are the canonical
foundation records.

The canonical records MUST be created as soon as a run directory is selected,
before external tool validation or any heavy stage starts. They MUST be updated
after each stage starts, completes, fails, or is skipped so an interrupted run
can be resumed without relying on terminal history.

## `cli_overrides.json`

Required fields:
- `overrides`: list of `{key, raw_value, parsed_value, source}`.
- `project_dir_override`: value supplied through `--project-dir`, if any.
- `requested_steps`: step list supplied through `--steps`, if any.
- `resume_policy`: value supplied through `--resume-policy`, if any.
- `run_id`: value supplied through `--run-id` or selected from an unambiguous
  prior partial run, if any.

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
- `requested_steps`
- `detected_existing_outputs`: optional filesystem-derived stage state for
  resumed runs whose previous records are missing or incomplete.

## `run_status.json`

Required fields:
- `status`
- `current_stage`
- `last_completed_stage`
- `started_at`
- `ended_at`
- `updated_at`
- `warnings_count`
- `errors`
- `stage_statuses`: mapping of stage names to `pending`, `running`, `complete`,
  `partial`, `failed`, `interrupted`, `skipped`, or an explicit skip reason.
- `active_command`: optional external command metadata for the currently running
  stage.

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

`timings.json` is append-updated after each timing stage finishes. It MUST NOT
be written only at the end of a run.

## Config Diff Event

When a previous partial run differs from the requested effective config, record:
- `previous_run_id`
- `detected_at`
- `differences`: list of `{path, previous_value, requested_value, source}`
- `decision`: `continue`, `overwrite`, or `blocked`
- `interactive`: boolean

## Resume Event

When a requested step has prior partial or completed outputs, record:
- `step`
- `previous_run_id`
- `previous_status`
- `decision`: `continue`, `overwrite`, or `blocked`
- `source`: `interactive_prompt`, `resume_policy`, or `non_interactive_block`
- `detected_at`

## Existing Run Selection

`--run-id <id>` means reuse `<project.dir>/runs/<id>/` in place. The CLI MUST
fail if that run directory does not exist. When `--run-id` is not supplied but
resume discovery finds exactly one prior run requiring a `resume` or `overwrite`
decision, the CLI may reuse that run directory rather than creating a new one.
