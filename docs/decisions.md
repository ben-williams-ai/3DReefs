# Decisions

## 2026-06-10 - Pipeline Foundation Shape

- Branch: `001-pipeline-foundation`
- Decision: Use one primary `uv run main.py --config <config>` entrypoint that derives normal paths from `project.dir` and writes run records under `<project.dir>/runs/<run_id>/`.
- Reason: Later SfM and splatting runs need reproducible configs, clear overrides, and auditable outputs before expensive work starts.
- Consequences: Public configs use placeholders. Local dataset paths belong in local config copies.

## 2026-06-10 - CLI Parser

- Branch: `001-pipeline-foundation`
- Decision: Use Click for the executable CLI parser.
- Reason: The required direct dotted override syntax, such as `--splat.train.num_iters 20000`, needs reliable unknown-option capture.
- Consequences: The CLI remains a thin wrapper around importable `src/reefs/` modules.

## 2026-06-10 - Foundation Does Not Run Heavy Stages

- Branch: `001-pipeline-foundation`
- Decision: Feature 1 validates and records the future pipeline surface but does not run COLMAP, undistortion, patching, LFS training, cleanup, compression, or merge stages.
- Reason: The foundation must be testable quickly and must establish config, logging, status, resume, and tool-validation behaviour first.
- Consequences: Later features can plug real stage execution into the existing run-record and preflight substrate.

## 2026-06-10 - Config Sections

- Branch: `001-pipeline-foundation`
- Decision: Public config files use `project` and `tools` as the only mandatory top-level sections; all other settings live under `advanced`.
- Reason: The user should make only the minimum required decisions up front, while advanced defaults remain visible and overrideable without cluttering the mandatory setup surface.
- Consequences: Dotted overrides for non-mandatory settings include the `advanced.` prefix, for example `--advanced.splat.train.num_iters 20000`.
