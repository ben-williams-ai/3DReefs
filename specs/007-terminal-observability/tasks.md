# Tasks: Live Terminal Output

**Input**: Design documents from `specs/007-terminal-observability/`  
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/terminal-output.md`

## Phase 1: Setup

- [X] T001 Update `.specify/feature.json` and `AGENTS.md` to point at `specs/007-terminal-observability`.

## Phase 2: Tests First

- [X] T002 [P] Add unit tests for terminal reporter stage messages and tee output in `tests/unit/test_terminal_output.py`.
- [X] T003 [P] Add integration tests for mocked COLMAP/LFS/SOG output appearing in terminal and logs in `tests/integration/test_terminal_observability.py`.

## Phase 3: Implementation

- [X] T004 Add minimal terminal reporter helper in `src/reefs/logging/terminal.py`.
- [X] T005 Wire `RunRecorder` stage start/complete/fail events to terminal and `pipeline.log` in `src/reefs/runs/recorder.py`.
- [X] T006 Tee COLMAP subprocess output to terminal and `logs/colmap.log` in `src/reefs/colmap/runner.py`.
- [X] T007 Tee LFS subprocess output to terminal, global LFS log, and patch log in `src/reefs/lfs/runner.py`.
- [X] T008 Tee SOG export subprocess output to terminal and SOG log in `src/reefs/postprocess/sog.py`.
- [X] T009 Add coarse messages around internal splat and postprocess stages in `src/reefs/splat/pipeline.py` and `src/reefs/postprocess/pipeline.py`, including per-patch camera selection, export, diagnostics, and validation messages during `splat.patch`.
- [X] T010 Wire the reporter from the CLI into the recorder and pipeline runners in `src/reefs/cli.py`.

## Phase 4: Verification

- [X] T011 Run focused terminal observability tests with `uv run pytest tests/unit/test_terminal_output.py tests/integration/test_terminal_observability.py -q`.
- [X] T012 Run the relevant existing pipeline tests with `uv run pytest tests/unit/test_colmap_commands.py tests/unit/test_lfs_status.py tests/integration/test_splat_mocked_success.py tests/integration/test_postprocess_mocked_success.py -q`.
- [X] T013 Run a bounded CLI smoke check or document why it was not run. Completed via `tests/integration/test_terminal_observability.py`.

## Dependencies

- T002 and T003 before T004-T010.
- T004 before T005-T010.
- T011-T013 after implementation.

## MVP

T002, T004, T005, T006, and T007 are the minimum useful slice: stage messages plus COLMAP/LFS live output.
