# Feature Specification: Pipeline Foundation

**Feature Branch**: `001-pipeline-foundation`  
**Created**: 2026-06-10  
**Status**: Draft  
**Input**: User description: "Create Feature 1: Pipeline Foundation for 3DReefs. Cover the user-visible ability to run the future reef SfM/3DGS pipeline from one uv command using --config, with project.dir in the config as the dataset/project directory and optional --project-dir as an override. Include config validation, derived paths, CLI overrides, run records, resume/start-over behaviour, external tool validation, and public-safe example configs. Exclude actual COLMAP reconstruction, matching, undistortion, patching, and LichtFeld Studio training."

## Clarifications

### Session 2026-06-10

- Q: How should resume/start-over decisions behave when a partial run is detected in a non-interactive run? → A: Prompt in interactive runs; fail in non-interactive runs unless an explicit resume/start-over flag is provided.
- Q: How should changed settings be handled when resuming a partial run? → A: Detect all setting differences during preflight before running any stage, show the differences to the user, require an explicit continue-or-overwrite decision, and record the differences and decision in the run logs and config/override records.
- Q: How should resume/start-over prompts behave when a user requests one or more specific pipeline steps? → A: The CLI preflight must inspect every requested step before running anything, prompt separately for each step that has prior partial or completed outputs, and finish all prompting before any requested step starts.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Start A Reproducible Pipeline Run (Priority: P1)

A reef reconstruction researcher can start a pipeline run from a single command that points to a config file. The config identifies the dataset/project directory, and the system derives the expected input and output locations from that directory.

**Why this priority**: This is the foundation for every later SfM and splatting feature. Without a reproducible run entrypoint and predictable project directory handling, later stages will inherit fragile path and logging behaviour.

**Independent Test**: Can be tested with a minimal valid config and a prepared project directory containing `raw_images/`. The command should validate inputs, create a run record, and stop before heavy SfM or splatting work.

**Acceptance Scenarios**:

1. **Given** a valid config with `project.dir` pointing to a project directory containing `raw_images/`, **When** the researcher starts a run with `--config`, **Then** the system validates the config, derives the required input/output paths, creates a new run record, and reports that foundation checks completed.
2. **Given** a valid config and a `--project-dir` override, **When** the researcher starts a run, **Then** the override is used for derived project paths and is recorded as an override in the run record.
3. **Given** a public example config, **When** it is inspected, **Then** it uses placeholders rather than private local dataset paths.

---

### User Story 2 - Override Config Values Safely (Priority: P2)

A researcher can override any supported config value from the command line for experiments while preserving a record of the original config, the overrides, and the effective values used for the run.

**Why this priority**: Large reef experiments need repeatable ablations. If overrides are not captured clearly, later results cannot be trusted or compared.

**Independent Test**: Can be tested by running a foundation-only command with a known config and one or more override arguments, then checking that the effective config and override record reflect the requested changes.

**Acceptance Scenarios**:

1. **Given** a config where an advanced setting has a default value, **When** the researcher supplies a valid override such as `--advanced.splat.train.num_iters 20000`, **Then** the effective run settings use the override and the override is recorded separately from the source config.
2. **Given** an override for an unknown config key, **When** the researcher starts a run, **Then** the system fails before creating expensive outputs and explains which override key is invalid.
3. **Given** multiple overrides, **When** the researcher starts a run, **Then** all accepted overrides are visible in the run record and in the effective settings for that run.

---

### User Story 3 - Resume Or Restart Partial Runs Explicitly (Priority: P3)

A researcher returning to an interrupted run is told what previously completed and must explicitly choose whether to continue from that state or start over.

**Why this priority**: Reef SfM and splatting runs are expensive. Silent restarts or ambiguous resumes can waste days of compute and make results impossible to audit.

**Independent Test**: Can be tested with a simulated partial run record. The next invocation should detect the partial state, present the previous progress, warn about relevant config changes, and require a resume or restart decision.

**Acceptance Scenarios**:

1. **Given** a project directory with a partial previous run, **When** the researcher starts another run for the same project, **Then** the system reports the previous run state and asks whether to resume or start over before any pipeline step starts.
2. **Given** a partial previous run and changed config values, **When** the researcher starts another run for the same project, **Then** the system detects all setting differences during preflight before running any stage, shows the differences, and requires an explicit continue-or-overwrite decision.
3. **Given** a researcher chooses to start over, **When** existing generated outputs could be overwritten, **Then** the system requires explicit confirmation before destructive overwrite behaviour proceeds.
4. **Given** a partial previous run and no interactive terminal, **When** the researcher starts another run without an explicit resume or start-over choice, **Then** the system fails early with instructions for making the decision explicitly.
5. **Given** a researcher requests one or more specific pipeline steps from the CLI, **When** any requested step has partial or completed prior outputs, **Then** the system checks each requested step individually, gathers all required resume/overwrite decisions up front, and starts no step until all required decisions are resolved.

---

### User Story 4 - Validate External Tools Without Heavy Work (Priority: P4)

A researcher can check that required external tools and versions are available before launching expensive reconstruction or training work.

**Why this priority**: Later features depend on COLMAP and LichtFeld Studio, but this foundation feature should only prove that the configured tools are available and compatible enough to plan a run.

**Independent Test**: Can be tested on a machine with valid and invalid tool paths. Valid tools should pass version/help checks; invalid paths or unsupported versions should fail before heavy work starts.

**Acceptance Scenarios**:

1. **Given** configured tool paths for COLMAP and LichtFeld Studio, **When** the researcher starts a foundation check, **Then** the system verifies the configured paths and target versions without running reconstruction, matching, undistortion, patching, or training.
2. **Given** SOG output is enabled for a future run, **When** the researcher starts a foundation check, **Then** the system verifies the configured SOG conversion tool is available.
3. **Given** a required tool is missing or reports an unsupported version, **When** the researcher starts a run, **Then** the system fails early with a clear explanation.

### Edge Cases

- The config file is missing, unreadable, malformed, or contains values of the wrong type.
- `project.dir` is missing, points to a non-directory, or does not contain `raw_images/`.
- `raw_images/` contains both direct images and camera subfolders, making the camera layout ambiguous.
- `project.recolour_images` is true but `recoloured_images/` is missing or does not mirror `raw_images/`. Recoloured images are validated for later undistortion/LFS/splatting use; COLMAP SfM continues to use raw images in later features.
- A command-line override targets an unknown setting or provides a value that fails validation.
- A previous run exists but its status record is incomplete or inconsistent with the files on disk.
- A requested run has config or override values that differ from a previous partial run's effective config.
- A partial run is detected in a non-interactive context without an explicit resume or start-over choice.
- A generated run directory already exists for the selected run identifier.
- A configured external tool path exists but reports the wrong version or lacks required capabilities.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow a researcher to start the foundation workflow with one command that references a config file.
- **FR-002**: The config MUST present mandatory settings first, with only `project` and `tools` as top-level mandatory sections. `project` MUST include `project.dir` as the dataset/project directory and `project.recolour_images` as the user-facing recoloured-image switch, and `tools` MUST include the configured COLMAP, LichtFeld Studio, and SOG conversion tool commands.
- **FR-003**: The system MUST derive the normal raw image input, optional recoloured image input, and generated run output locations from `project.dir`.
- **FR-004**: The system MUST allow an optional `--project-dir` command-line override and record that override when used.
- **FR-005**: The system MUST validate that `raw_images/` exists under the resolved project directory before any later pipeline work can begin.
- **FR-006**: The system MUST infer single-camera input when images are directly inside `raw_images/` and multi-camera input when camera subfolders are inside `raw_images/`.
- **FR-007**: The system MUST reject ambiguous image organisation, including layouts that mix direct images and camera subfolders in `raw_images/`.
- **FR-008**: When `project.recolour_images` is true, the system MUST validate that `recoloured_images/` mirrors the raw image layout and filenames for later undistortion/LFS/splatting use; this MUST NOT imply that later COLMAP SfM stages use recoloured images.
- **FR-009**: The system MUST accept supported command-line overrides for config values and apply them to the effective settings for the run.
- **FR-010**: The system MUST reject unknown or invalid command-line override keys before creating expensive outputs.
- **FR-011**: The system MUST write the source config, effective config, command-line overrides, run manifest, run status, timing records, and general logs for each run.
- **FR-012**: The system MUST record external tool paths, detected versions, and validation results in the run record.
- **FR-013**: The system MUST validate configured COLMAP and LichtFeld Studio tools against the target versions before heavy work begins.
- **FR-014**: The system MUST validate the SOG conversion tool only when SOG output is enabled for the configured run.
- **FR-015**: The foundation workflow MUST NOT run COLMAP reconstruction, feature matching, image undistortion, patch generation, LichtFeld Studio training, cleanup, compression, or merge stages.
- **FR-016**: The system MUST detect previous partial runs for the same project and present the prior status before continuing.
- **FR-017**: The system MUST require an explicit resume or start-over decision when partial previous outputs are detected, before any requested pipeline step starts.
- **FR-018**: The system MUST compare the requested effective config against the previous partial run's effective config during preflight, before running any stage.
- **FR-019**: The system MUST require explicit confirmation before overwriting generated outputs from an existing run.
- **FR-020**: Public example configs MUST use placeholders and MUST NOT contain private dataset paths, credentials, or machine-specific absolute dataset locations.
- **FR-021**: When a partial run is detected in a non-interactive context, the system MUST fail before continuing unless the researcher supplied an explicit resume or start-over choice.
- **FR-022**: When config values differ from a previous partial run, the system MUST show the differences, require an explicit continue-or-overwrite decision, and record the differences and decision in the run logs and config/override records.
- **FR-023**: When the researcher requests specific pipeline steps from the CLI, the system MUST inspect each requested step for prior partial or completed outputs during preflight and resolve all required decisions before running any requested step.
- **FR-024**: All non-mandatory config settings MUST be grouped below a clearly labelled `advanced` section in public examples and effective configs.

### Key Entities *(include if feature involves data)*

- **Pipeline Config**: User-provided settings that identify the project directory, recoloured-image behaviour, future pipeline settings, and external tool configuration.
- **Project Directory**: Dataset root containing required `raw_images/`, optional `recoloured_images/`, and generated run outputs.
- **CLI Override**: A command-line setting that changes a config value for a single run and must be recorded separately from the source config.
- **Effective Config**: The resolved settings used for a run after defaults and accepted overrides are applied.
- **Run Record**: The collection of manifest, status, timings, logs, config snapshots, tool validation results, and warnings for a single pipeline attempt.
- **Partial Run**: A previous run record or output set that indicates some stages started or completed but the full requested workflow did not finish.
- **Tool Validation Result**: The recorded outcome of checking required external tool paths, versions, and available capabilities.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A researcher can run a foundation check from a valid config and receive a clear pass/fail result without starting any heavy SfM or splatting stage.
- **SC-002**: For every successful foundation run, the run record contains the effective settings, override record, tool validation results, timing information, status, and logs.
- **SC-003**: Invalid configs, missing required folders, unknown overrides, and missing or unsupported tools fail before any heavy external processing begins.
- **SC-004**: A partial-run restart or resume attempt detects config differences before running any stage and records the user's decision plus the detected differences.
- **SC-005**: Public example configs can be reviewed without exposing private paths, credentials, or local dataset locations.

## Assumptions

- The researcher is running commands from the 3DReefs repository on a Linux workstation prepared for the later COLMAP and LichtFeld Studio stages.
- This feature establishes run setup and validation only; later features will implement actual SfM, undistortion, patching, training, cleanup, compression, and merge behaviour.
- The target external tools for validation are COLMAP `4.0.4` and LichtFeld Studio `v0.5.2`.
- `raw_images/` is the only required dataset input folder for the foundation feature.
- Recoloured images are optional and are validated only when the config requests them. They are intended for later undistortion/LFS/splatting inputs, not for later raw-image COLMAP SfM.
