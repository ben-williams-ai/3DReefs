# Tasks: Pipeline Foundation

**Input**: Design documents from `specs/001-pipeline-foundation/`  
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`

**Tests**: Included because the constitution and plan require focused automated tests for config parsing, path resolution, command construction, status detection, output selection, and resume logic.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel with other tasks in the same phase when files do not overlap
- **[Story]**: User story label for story-specific tasks only

## Phase 1: Setup

**Purpose**: Create the Python project scaffold and placeholder config/documentation structure.

- [ ] T001 Create Python package scaffold in `src/reefs/__init__.py`, `src/reefs/cli.py`, and `main.py`
- [ ] T002 Create module directories with `__init__.py` files in `src/reefs/config/`, `src/reefs/io/`, `src/reefs/logging/`, `src/reefs/preflight/`, and `src/reefs/runs/`
- [ ] T003 Configure Python project metadata and dependencies in `pyproject.toml`
- [ ] T004 Generate or update `uv.lock` from `pyproject.toml`
- [ ] T005 [P] Create placeholder dataset configs in `configs/example.yml` and `configs/datasets/dataset_01.yml`
- [ ] T006 [P] Create placeholder dataset configs in `configs/datasets/dataset_02.yml`, `configs/datasets/dataset_03.yml`, `configs/datasets/dataset_04.yml`, and `configs/datasets/dataset_05.yml`
- [ ] T007 [P] Create test package scaffolding in `tests/unit/` and `tests/integration/`

---

## Phase 2: Foundational

**Purpose**: Implement shared primitives that every user story depends on.

**Critical**: No user story work should begin until this phase is complete.

- [ ] T008 Define typed config models in `src/reefs/config/models.py`
- [ ] T009 Implement YAML/JSON helpers in `src/reefs/io/yaml_json.py`
- [ ] T010 Implement project path derivation primitives in `src/reefs/io/paths.py`
- [ ] T011 Implement timing record primitives in `src/reefs/logging/timings.py`
- [ ] T012 Implement run status primitives in `src/reefs/runs/status.py`
- [ ] T013 Implement run manifest primitives in `src/reefs/runs/manifest.py`
- [ ] T014 Implement human-readable pipeline/warnings log setup in `src/reefs/logging/run_logger.py`
- [ ] T015 Implement top-level preflight orchestration shell in `src/reefs/preflight/validation.py`
- [ ] T016 Wire `main.py` to delegate to `reefs.cli` without business logic in `main.py`

**Checkpoint**: Shared models, IO, run records, logging, and CLI entrypoint shell exist.

---

## Phase 3: User Story 1 - Start A Reproducible Pipeline Run (Priority: P1)

**Goal**: A researcher can run `uv run main.py --config <config.yml>` against a project containing `raw_images/`, derive project-local paths, create a run directory, write run records, and stop before heavy SfM/splatting work.

**Independent Test**: Run the command with a minimal valid config and project directory containing `raw_images/`; it should write foundation records and not start COLMAP/LFS processing.

### Tests for User Story 1

- [ ] T017 [P] [US1] Add config loading tests for valid, missing, malformed, and wrong-type configs in `tests/unit/test_config_loader.py`
- [ ] T018 [P] [US1] Add project path derivation tests for `raw_images/`, `recoloured_images/`, and `runs/` under `project.dir` in `tests/unit/test_project_paths.py`
- [ ] T019 [P] [US1] Add image layout tests for single-camera, multi-camera, mixed invalid layouts, and recoloured-image mirror validation in `tests/unit/test_image_layout.py`
- [ ] T020 [P] [US1] Add integration test for a valid foundation run creating required records, including `reports/preflight_report.md`, in `tests/integration/test_foundation_valid_project.py`

### Implementation for User Story 1

- [ ] T021 [US1] Implement config loading, default application, and validation in `src/reefs/config/loader.py`
- [ ] T022 [US1] Implement single-camera, multi-camera, ambiguous image layout detection, and optional `recoloured_images/` mirror validation in `src/reefs/preflight/images.py`
- [ ] T023 [US1] Implement run directory creation and required record file path generation in `src/reefs/runs/manifest.py`
- [ ] T024 [US1] Implement run status writing for foundation-only runs in `src/reefs/runs/status.py`
- [ ] T025 [US1] Implement effective config writing in `src/reefs/config/loader.py`
- [ ] T026 [US1] Implement timing capture for foundation substages in `src/reefs/logging/timings.py`
- [ ] T027 [US1] Implement CLI command handling for `--config` in `src/reefs/cli.py`
- [ ] T028 [US1] Implement preflight report writing to `reports/preflight_report.md` in `src/reefs/preflight/validation.py`
- [ ] T029 [US1] Add example config comments and public-safe placeholders in `configs/example.yml`
- [ ] T030 [US1] Add dataset placeholder configs with public-safe project placeholders in `configs/datasets/dataset_01.yml`, `configs/datasets/dataset_02.yml`, `configs/datasets/dataset_03.yml`, `configs/datasets/dataset_04.yml`, and `configs/datasets/dataset_05.yml`

**Checkpoint**: User Story 1 is independently functional and testable.

---

## Phase 4: User Story 2 - Override Config Values Safely (Priority: P2)

**Goal**: A researcher can pass dotted CLI overrides and `--project-dir`, have accepted values reflected in the effective config, and have invalid override keys fail before output creation.

**Independent Test**: Run a foundation command with known overrides and inspect `effective_config.yml` plus `cli_overrides.json`; unknown overrides should fail early.

### Tests for User Story 2

- [ ] T031 [P] [US2] Add dotted override parsing tests for valid keys, type coercion, and unknown keys in `tests/unit/test_cli_overrides.py`
- [ ] T032 [P] [US2] Add `--project-dir`, `--steps`, and `--resume-policy` override tests in `tests/unit/test_cli_overrides.py`
- [ ] T033 [P] [US2] Add integration test for override persistence in `tests/integration/test_foundation_overrides.py`

### Implementation for User Story 2

- [ ] T034 [US2] Implement dotted CLI override parsing in `src/reefs/config/overrides.py`
- [ ] T035 [US2] Implement override validation against typed config models in `src/reefs/config/overrides.py`
- [ ] T036 [US2] Implement `--project-dir`, `--steps`, and `--resume-policy` handling and recording in `src/reefs/cli.py`
- [ ] T037 [US2] Implement `cli_overrides.json` writing in `src/reefs/runs/manifest.py`
- [ ] T038 [US2] Integrate accepted overrides into effective config generation in `src/reefs/config/loader.py`
- [ ] T039 [US2] Ensure unknown or invalid overrides fail before run output creation in `src/reefs/cli.py`

**Checkpoint**: User Story 2 is independently functional and testable after User Story 1.

---

## Phase 5: User Story 3 - Resume Or Restart Partial Runs Explicitly (Priority: P3)

**Goal**: A researcher returning to a partial run sees previous progress, config differences are detected before any stage runs, and interactive/non-interactive decisions are handled safely.

**Independent Test**: Use a simulated partial run record, invoke the foundation command, and verify prompt/failure behaviour plus config diff recording.

### Tests for User Story 3

- [ ] T040 [P] [US3] Add partial run discovery tests for complete, partial, missing, and corrupt status records in `tests/unit/test_resume_decisions.py`
- [ ] T041 [P] [US3] Add effective config diff tests in `tests/unit/test_resume_decisions.py`
- [ ] T042 [P] [US3] Add non-interactive decision failure and explicit `--resume-policy` tests in `tests/unit/test_resume_decisions.py`
- [ ] T043 [P] [US3] Add integration test for partial-run resume safety, including multiple requested steps prompting before any step runs, in `tests/integration/test_foundation_partial_run.py`

### Implementation for User Story 3

- [ ] T044 [US3] Implement partial run discovery per requested step in `src/reefs/runs/resume.py`
- [ ] T045 [US3] Implement previous effective config loading and requested effective config comparison in `src/reefs/runs/resume.py`
- [ ] T046 [US3] Implement config diff event modelling and serialisation in `src/reefs/runs/resume.py`
- [ ] T047 [US3] Implement interactive continue-or-overwrite prompt handling that resolves all requested-step decisions before any step runs in `src/reefs/cli.py`
- [ ] T048 [US3] Implement non-interactive failure when explicit `--resume-policy` intent is absent in `src/reefs/cli.py`
- [ ] T049 [US3] Implement resume/overwrite decision recording in `run_manifest.json` via `src/reefs/runs/manifest.py`
- [ ] T050 [US3] Implement append-safe log behaviour for resumed runs in `src/reefs/logging/run_logger.py`

**Checkpoint**: User Story 3 is independently functional and testable after User Stories 1 and 2.

---

## Phase 6: User Story 4 - Validate External Tools Without Heavy Work (Priority: P4)

**Goal**: A researcher can validate configured COLMAP, LichtFeld Studio, and conditional SOG conversion tools by path/version/capability checks without starting heavy external processing.

**Independent Test**: Use mocked valid and invalid tool commands; valid checks pass and invalid paths/versions fail before heavy work starts.

### Tests for User Story 4

- [ ] T051 [P] [US4] Add COLMAP version and help validation tests with mocked subprocess output in `tests/unit/test_tool_validation.py`
- [ ] T052 [P] [US4] Add LichtFeld Studio version/help validation tests with mocked subprocess output in `tests/unit/test_tool_validation.py`
- [ ] T053 [P] [US4] Add conditional SOG conversion tool validation tests in `tests/unit/test_tool_validation.py`
- [ ] T054 [P] [US4] Add integration test proving no heavy external command is invoked in `tests/integration/test_foundation_tool_validation.py`

### Implementation for User Story 4

- [ ] T055 [US4] Implement bounded subprocess helper for version/help commands in `src/reefs/preflight/tools.py`
- [ ] T056 [US4] Implement COLMAP `4.0.4` validation without running reconstruction in `src/reefs/preflight/tools.py`
- [ ] T057 [US4] Implement LichtFeld Studio `v0.5.2` validation without running training in `src/reefs/preflight/tools.py`
- [ ] T058 [US4] Implement conditional SOG conversion tool validation in `src/reefs/preflight/tools.py`
- [ ] T059 [US4] Record tool validation results in run manifest and timings via `src/reefs/runs/manifest.py` and `src/reefs/logging/timings.py`
- [ ] T060 [US4] Integrate tool validation into preflight orchestration in `src/reefs/preflight/validation.py`

**Checkpoint**: User Story 4 is independently functional and testable after User Story 1.

---

## Final Phase: Polish & Cross-Cutting Concerns

**Purpose**: Finish documentation, consistency checks, and validation commands.

- [ ] T061 [P] Update `README.MD` with the Feature 1 command and expected foundation-only behaviour
- [ ] T062 [P] Update `docs/decisions.md` with the pipeline foundation decisions if the file exists, or create it if absent
- [ ] T063 [P] Add troubleshooting notes for invalid config, ambiguous image layout, missing tools, and partial-run conflicts in `docs/troubleshooting.md`
- [ ] T064 Run `uv run pytest tests/unit tests/integration` and record any failures in the final implementation summary
- [ ] T065 Run quickstart validation from `specs/001-pipeline-foundation/quickstart.md`
- [ ] T066 Run `rg` checks to ensure public configs/docs do not contain private dataset paths or credentials
- [ ] T067 Resolve accepted `speckit-analyze` findings before implementation handoff or before declaring artifacts ready

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: no dependencies.
- **Phase 2 Foundational**: depends on Phase 1 and blocks all user stories.
- **Phase 3 US1**: depends on Phase 2 and is the MVP.
- **Phase 4 US2**: depends on US1 config/run-record foundation.
- **Phase 5 US3**: depends on US1 and US2 because resume compares effective config and overrides.
- **Phase 6 US4**: depends on US1 run-record foundation and can proceed in parallel with US2/US3 after US1.
- **Final Phase**: depends on desired story completion.

### User Story Dependencies

- **US1 Start A Reproducible Pipeline Run**: first deliverable and MVP.
- **US2 Override Config Values Safely**: builds on US1 effective config and run records.
- **US3 Resume Or Restart Partial Runs Explicitly**: builds on US1 run records and US2 effective config diffing.
- **US4 Validate External Tools Without Heavy Work**: builds on US1 run records; independent of US2/US3 once US1 exists.

### Parallel Opportunities

- Setup directory/config scaffolding tasks T005-T007 can run in parallel after T001-T004.
- Foundational primitives T008-T014 can be split by module after package scaffolding exists.
- US1 test tasks T017-T020 can run in parallel.
- US2 test tasks T031-T033 can run in parallel.
- US3 test tasks T040-T043 can run in parallel.
- US4 test tasks T051-T054 can run in parallel.
- US4 implementation can proceed in parallel with US2/US3 after US1 completes.
- Polish documentation tasks T061-T063 can run in parallel after user stories are implemented.

---

## Parallel Examples

### User Story 1

```text
Task: "T017 Add config loading tests in tests/unit/test_config_loader.py"
Task: "T018 Add project path derivation tests in tests/unit/test_project_paths.py"
Task: "T019 Add image layout tests in tests/unit/test_image_layout.py"
Task: "T020 Add integration test in tests/integration/test_foundation_valid_project.py"
```

### User Story 3

```text
Task: "T040 Add partial run discovery tests in tests/unit/test_resume_decisions.py"
Task: "T041 Add effective config diff tests in tests/unit/test_resume_decisions.py"
Task: "T042 Add non-interactive decision failure tests in tests/unit/test_resume_decisions.py"
Task: "T043 Add integration test in tests/integration/test_foundation_partial_run.py"
```

### User Story 4

```text
Task: "T051 Add COLMAP validation tests in tests/unit/test_tool_validation.py"
Task: "T052 Add LichtFeld Studio validation tests in tests/unit/test_tool_validation.py"
Task: "T053 Add SOG conversion validation tests in tests/unit/test_tool_validation.py"
Task: "T054 Add no-heavy-command integration test in tests/integration/test_foundation_tool_validation.py"
```

---

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 only.
3. Validate that `uv run main.py --config <config.yml>` loads a config, derives paths, creates run records, and does not run heavy stages.
4. Stop and review before adding overrides, resume logic, or tool validation.

### Incremental Delivery

1. Deliver US1 for the basic foundation run.
2. Add US2 for reproducible override handling.
3. Add US3 for safe partial-run recovery.
4. Add US4 for bounded external tool validation.
5. Run polish tasks and `speckit-analyze`.
