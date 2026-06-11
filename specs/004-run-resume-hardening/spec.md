# Feature Specification: Run Resume Hardening

**Feature Branch**: `004-run-resume-hardening`  
**Created**: 2026-06-11  
**Status**: Implemented  
**Input**: Harden run records and resume behaviour so long COLMAP and future LFS jobs remain auditable and resumable after interruption.

## User Scenarios & Testing

### User Story 1 - Durable Records For Long Runs

A researcher starts a long pipeline stage and can inspect the run directory while it is still running or after interruption.

**Acceptance Scenarios**:

1. **Given** a run has just started, **When** external tool validation has not yet completed, **Then** `effective_config.yml`, `cli_overrides.json`, `run_manifest.json`, `run_status.json`, and `timings.json` already exist.
2. **Given** a stage is running, **When** the researcher opens `run_status.json`, **Then** it identifies the current stage and any active external command.
3. **Given** a stage completes, **When** the researcher opens the run records, **Then** status and timings show that stage as complete.

### User Story 2 - Resume A Named Run In Place

A researcher can resume or overwrite a specific interrupted run without creating a new run directory.

**Acceptance Scenarios**:

1. **Given** an interrupted run directory exists, **When** the researcher supplies `--run-id`, **Then** the pipeline reuses that run directory.
2. **Given** undistortion is partial, **When** the researcher requests `sfm.undistort` with overwrite, **Then** the partial generated undistortion output is removed and undistortion reruns in the same run directory.
3. **Given** `--run-id` names a missing run, **When** the command starts, **Then** the pipeline fails before heavy work.

### User Story 3 - Recover From Missing Or Stale Records

A researcher can recover older interrupted runs whose final records were never written.

**Acceptance Scenarios**:

1. **Given** SfM filesystem outputs exist but canonical records are missing, **When** the researcher resumes that run, **Then** the pipeline infers completed or partial SfM stage state from generated outputs.
2. **Given** the previous status claimed only a coarse stage, **When** the run is resumed or inspected, **Then** the new status uses specific stage names such as `sfm.preflight` or `sfm.undistort`.

## Requirements

- **FR-001**: The system MUST write canonical records immediately after selecting a run directory.
- **FR-002**: The system MUST update status and timings after each stage starts, completes, fails, or is interrupted.
- **FR-003**: The system MUST support `--run-id` for resuming or overwriting a specific existing run directory.
- **FR-004**: The system MUST fail early when `--run-id` refers to a missing run directory.
- **FR-005**: The system MUST avoid creating a new run directory when an explicit or unambiguous resume targets an existing run.
- **FR-006**: The system MUST infer SfM stage state from filesystem outputs when previous records are missing or incomplete.
- **FR-007**: The system MUST not report `sfm.preflight` as full `sfm` completion.
- **FR-008**: The system MUST stream COLMAP command output to `logs/colmap.log` while commands run.
- **FR-009**: The system MUST support resume/rerun at explicit COLMAP stage boundaries while making clear that interrupted COLMAP subprocesses restart from the beginning of that stage.
- **FR-010**: The system MUST fail before running later SfM stages when their required prior outputs, such as the COLMAP database or selected sparse model, are missing.

## Out Of Scope

- New COLMAP reconstruction behaviour.
- New LFS training, patching, cleanup, SOG, or merging behaviour.
- Reworking historical run directories beyond enabling safe resume commands.
