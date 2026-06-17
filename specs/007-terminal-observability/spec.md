# Feature Specification: Live Terminal Output

**Feature Branch**: `007-terminal-observability`  
**Created**: 2026-06-17  
**Status**: Draft  
**Input**: User description: "Live terminal observability across the full 3DReefs pipeline while keeping durable logs."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See Pipeline Progress Live (Priority: P1)

As a researcher running a long reef pipeline from the terminal, I need the command to show which stage is currently running and when each stage completes, so I can tell that the job is alive without opening JSON records or guessing from fan noise.

**Why this priority**: This fixes the immediate failure mode where patching, outlier filtering, or other long internal work can run silently for many minutes.

**Independent Test**: Run a mocked pipeline with requested SfM and splat stages and confirm the terminal shows each stage starting and completing before the final completion message.

**Acceptance Scenarios**:

1. **Given** a user starts a full pipeline run, **When** foundation checks, SfM, patching, training, cleanup, merge, or SOG stages start, **Then** the terminal shows a clear stage-start message.
2. **Given** a stage completes, **When** the pipeline advances, **Then** the terminal shows that stage completed and includes elapsed time.
3. **Given** a Python-only stage has no external tool output, **When** it runs for a while, **Then** the terminal still shows coarse messages for important substeps such as outlier filtering, patch generation, selected patch count, and per-patch work.
4. **Given** patch generation is running, **When** each patch is processed, **Then** the terminal shows the patch id and whether it is selecting cameras, exporting the patch dataset, writing diagnostics, or finished validation.

---

### User Story 2 - See External Tool Output Live (Priority: P1)

As a user running COLMAP, LFS, or SOG export, I need the normal tool output to appear in the terminal while it is also saved to logs, so I can follow progress and spot failures immediately.

**Why this priority**: COLMAP and LFS already produce useful progress. Hiding that output makes long runs feel stuck and forces users to chase log files.

**Independent Test**: Run mocked external commands that emit stdout/stderr and confirm the same output appears in the terminal and the appropriate log file.

**Acceptance Scenarios**:

1. **Given** a COLMAP command emits progress, **When** it runs through the pipeline, **Then** the progress appears live in the terminal and in the COLMAP log.
2. **Given** an LFS patch training command emits iteration/loss output, **When** it runs, **Then** the output appears live in the terminal and remains saved in the global and patch logs.
3. **Given** a SOG export command emits output, **When** it runs, **Then** the output appears live in the terminal and remains saved in the SOG log.

---

### User Story 3 - Understand Failures And Interruptions (Priority: P2)

As a user who stops a run or hits an error, I need the terminal to say which stage was interrupted or failed while the run records remain recoverable.

**Why this priority**: Long runs are often resumed. A visible failure stage reduces confusion and supports the existing resume workflow.

**Independent Test**: Simulate a failing or interrupted stage and confirm the terminal shows the failed/interrupted stage and run status is persisted.

**Acceptance Scenarios**:

1. **Given** a user presses Ctrl-C, **When** the pipeline handles the interrupt, **Then** the terminal shows the current interrupted stage and the run status records the interruption.
2. **Given** an external tool exits non-zero, **When** the pipeline fails the stage, **Then** the terminal shows the failed stage and the existing logs still contain the tool output.

### Edge Cases

- Output must not be duplicated excessively in terminal or logs.
- Runs must still work in tmux or a normal terminal without needing a second `tail -f` window.
- If an external tool produces no output for a period, stage-start messages must still make it clear what the pipeline is waiting on.
- Preflight-only runs must print preflight progress and must not imply the whole SfM or splat pipeline completed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST print a live stage-start message for every requested foundation, SfM, splat, cleanup, merge, and SOG stage.
- **FR-002**: The system MUST print a live stage-completion message with elapsed time for every completed stage.
- **FR-003**: The system MUST mirror COLMAP stdout/stderr to the terminal while preserving the COLMAP log.
- **FR-004**: The system MUST mirror LFS stdout/stderr to the terminal while preserving the global LFS log and patch-local training log.
- **FR-005**: The system MUST mirror SOG export stdout/stderr to the terminal while preserving the SOG export log.
- **FR-006**: The system MUST print coarse progress for long Python-only stages that do not naturally emit external command output.
- **FR-007**: The system MUST print the current stage when a run fails or is interrupted.
- **FR-008**: The system MUST keep existing run manifests, statuses, timings, and logs as durable records.
- **FR-009**: The system MUST NOT add a required config switch for terminal output in this feature; live terminal output is the default.
- **FR-010**: During patch generation, the system MUST print per-patch progress for camera selection, selected camera/sparse-point counts, patch dataset export, diagnostic writing, and final patch validity.

### Key Entities

- **Terminal Event**: A live user-facing message for stage starts, completions, failures, coarse progress, or external tool output.
- **Durable Log Entry**: The existing file-backed record that remains available after the command exits.
- **Pipeline Stage**: A named unit of work such as `sfm.undistort`, `splat.patch`, or `splat.train`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A mocked multi-stage pipeline run shows terminal output within 2 seconds of each stage start.
- **SC-002**: 100% of mocked COLMAP, LFS, and SOG output lines appear in both terminal capture and the corresponding log file.
- **SC-003**: A splat-only trial run shows visible terminal progress before any LFS process starts.
- **SC-004**: A simulated failure or interruption reports the active stage in terminal output and persists failed/interrupted run status.
- **SC-005**: A mocked patching run shows per-patch messages for camera selection, patch export, and validation before training begins.

## Assumptions

- Terminal output is intended for interactive terminal and tmux use.
- No progress bars or estimated percentages are needed in this feature.
- Quiet or verbose modes can be added later if real usage shows the default output is too noisy.
