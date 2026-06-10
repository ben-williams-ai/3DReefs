# Research: Pipeline Foundation

## Decision: Use `src/reefs/` Package With Thin `main.py`

**Rationale**: The build guide asks for a normal Python project with `uv`, a simple
entrypoint, and reusable modules under `src/`. A package namespace avoids ambiguous
imports such as `config` or `logging` and gives tests a stable import target.

**Alternatives considered**:
- Put modules directly under `src/`: rejected because names like `logging`, `io`,
  and `config` collide with standard or common package names.
- Keep a single large script like the old repo runners: rejected because the old
  repo became difficult to refactor and test.

## Decision: Typed Config Model With YAML Input And Effective YAML Output

**Rationale**: The user-facing config is YAML with comments in examples, but the
runtime needs typed validation, defaults, path derivation, and CLI override
checking. A typed model provides early errors and a serialisable effective config.

**Alternatives considered**:
- Plain dictionaries: rejected because unknown keys and wrong value types are too
  easy to miss.
- JSON-only config: rejected because the user explicitly wants commented example
  configs.

## Decision: `project.dir` Is The Dataset Root; Normal Paths Are Derived

**Rationale**: The guide explicitly reduces mandatory settings to `project.dir` and
`project.recolour_images`. The old repo's project-local preprocessing tests support
the same lesson: derived project-local artefacts are easier to audit and clean up.

**Alternatives considered**:
- Require separate raw image, recoloured image, and output paths: rejected because
  it increases user error and makes inconsistent configs likely.
- Use only a CLI project path: rejected because reproducible configs need to carry
  the dataset root, with CLI override only for local experiments.

## Decision: CLI Overrides Are Parsed As Dotted Config Paths

**Rationale**: The guide requires overrides such as
`--splat.train.num_iters 20000`. Dotted keys are readable, map naturally onto the
config tree, and can be validated against the typed model before running.

**Alternatives considered**:
- A generic `--set key=value` interface: rejected for this project because the
  requested UX uses direct dotted flags.
- Allow unknown overrides and store them as metadata: rejected because typos must
  fail during preflight.

## Decision: Run Records Are Filesystem Documents Under Each Run Directory

**Rationale**: The pipeline is a local research workflow. JSON/YAML/Markdown/log
files are transparent, easy to inspect, easy to archive with outputs, and sufficient
for the foundation feature. The old repo had useful reports and timings but spread
them across scripts; the new layout makes them explicit.

**Alternatives considered**:
- SQLite run database: rejected as unnecessary for Feature 1 and harder to inspect
  manually.
- Logs only: rejected because stage status, config diffs, overrides, and timings
  need structured records.

## Decision: Resume Conflicts Are Detected During Preflight

**Rationale**: The spec clarifies that the previous effective config and requested
effective config must be compared before any stage runs. This prevents expensive
mixed-parameter runs and keeps config changes auditable.

**Alternatives considered**:
- Detect conflicts lazily when a stage starts: rejected because it may waste time
  and produce partial outputs before the conflict is noticed.
- Block all resumes with changed config: rejected because some changes may be
  deliberate and harmless if explicitly acknowledged.

## Decision: Tool Validation Uses Bounded Version/Help Checks Only

**Rationale**: Feature 1 must validate COLMAP `4.0.4`, LichtFeld Studio `v0.5.2`,
and optionally SOG conversion availability without starting heavy work. The old
repo's flag audit tests show help-output validation is useful, but target versions
and supported commands must be checked for the new installed tools rather than
assuming old CLI flags are still valid.

**Alternatives considered**:
- Run small real COLMAP/LFS jobs: rejected because the feature explicitly excludes
  heavy external processing.
- Defer all tool checks to later features: rejected because the constitution and
  spec require early external tool validation.

## Decision: Single-Camera And Multi-Camera Layout Are Inferred From `raw_images/`

**Rationale**: The guide says users should organise data appropriately and not set
camera mode unless they need advanced overrides. Direct images imply a single
camera; camera subfolders imply multi-camera.

**Alternatives considered**:
- Require `camera_config.multicam`: rejected as unnecessary mandatory config.
- Auto-accept mixed direct images and folders: rejected because it is ambiguous and
  likely indicates a dataset preparation error.
