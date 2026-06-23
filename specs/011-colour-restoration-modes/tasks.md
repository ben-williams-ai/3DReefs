# Tasks: Colour Restoration Modes

**Input**: Design documents from `specs/011-colour-restoration-modes/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Required by the feature specification. Write or update focused tests before implementation tasks in each user story.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Locate all legacy colour config references and establish the shared edit surface.

- [ ] T001 Review legacy `recolour_images` and `start_sfm_immediately` references in `src/reefs/`, `tests/`, `configs/`, `README.MD`, and `specs/010-image-recolour-workflow/`
- [ ] T002 [P] Confirm current colour pipeline entry points and reuse helpers in `src/reefs/cli.py` and `src/reefs/colour/pipeline.py`
- [ ] T003 [P] Confirm existing config load and override patterns in `src/reefs/config/models.py`, `src/reefs/config/loader.py`, and `src/reefs/config/overrides.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add the shared typed configuration and state vocabulary required by every mode.

- [ ] T004 Add `ColourRestorationMode` and `ColourRestorationConfig` in `src/reefs/config/models.py`
- [ ] T005 Move colour workflow settings out of `ProjectConfig` and add required root `colour_restoration` field in `src/reefs/config/models.py`
- [ ] T006 Preserve clear validation errors for forbidden legacy keys `project.recolour_images` and `project.start_sfm_immediately` in `src/reefs/config/models.py` or `src/reefs/config/loader.py`
- [ ] T007 Update CLI override support for `colour_restoration.mode`, `colour_restoration.overwrite`, and `colour_restoration.start_sfm_immediately` in `src/reefs/config/overrides.py`
- [ ] T008 Extend colour state metadata with restoration mode and relevant config fields in `src/reefs/colour/state.py`
- [ ] T009 Update shared test config writer to emit the top-level colour restoration block in `tests/conftest.py`

**Checkpoint**: The codebase can represent the new config shape before any mode-specific behaviour changes.

---

## Phase 3: User Story 1 - Choose Colour Restoration Explicitly (Priority: P1) MVP

**Goal**: Configs must use the required top-level colour restoration block, accept valid modes, default omitted mode to off, reject invalid modes, and fail clearly for legacy keys.

**Independent Test**: Load valid, invalid, missing, legacy, example, dataset, and test configs and inspect the typed config result or validation error.

### Tests for User Story 1

- [ ] T010 [P] [US1] Add config model tests for valid `off`, `gray_world`, and `manual` modes in `tests/unit/test_config_models.py`
- [ ] T011 [P] [US1] Add config loader tests for missing block failure, omitted mode defaulting to `off`, invalid mode failure, and legacy key failures in `tests/unit/test_config_loader.py`
- [ ] T012 [P] [US1] Add example config load coverage for `configs/example.yml`, `configs/test.yml`, and `configs/datasets/*.yml` in `tests/unit/test_config_loader.py`
- [ ] T013 [P] [US1] Update CLI override tests for top-level colour restoration overrides in `tests/unit/test_cli_overrides.py`

### Implementation for User Story 1

- [ ] T014 [US1] Replace all maintained config files with `colour_restoration.mode`, `overwrite`, and `start_sfm_immediately` in `configs/example.yml`, `configs/test.yml`, and `configs/datasets/*.yml`
- [ ] T015 [US1] Update config docs and generated examples to remove legacy `recolour_images` references in `README.MD` and `specs/010-image-recolour-workflow/contracts/cli.md`
- [ ] T016 [US1] Update tests and helpers to reference `config.colour_restoration` instead of `config.project.recolour_images` in `tests/`
- [ ] T017 [US1] Update code references from `config.project.recolour_images` and `config.project.start_sfm_immediately` to the new block in `src/reefs/cli.py`, `src/reefs/preflight/splat.py`, `src/reefs/sfm/pipeline.py`, and related modules
- [ ] T018 [US1] Run `uv run pytest tests/unit/test_config_loader.py tests/unit/test_config_models.py tests/unit/test_cli_overrides.py`

**Checkpoint**: User Story 1 is complete when configuration validation and examples behave exactly as specified.

---

## Phase 4: User Story 2 - Run Without Colour Restoration (Priority: P2)

**Goal**: `mode: off` bypasses colour state, GUI, apply orchestration, and restored outputs while reconstruction uses raw images.

**Independent Test**: Run an off-mode pipeline/preflight path and verify no colour state or restored output is created and raw images are selected.

### Tests for User Story 2

- [ ] T019 [P] [US2] Update off-mode pipeline integration tests in `tests/integration/test_colour_disabled_pipeline.py`
- [ ] T020 [P] [US2] Add raw-image handoff assertions for off mode in `tests/integration/test_sfm_recoloured_undistortion.py`
- [ ] T021 [P] [US2] Add splat preflight assertions that off mode ignores absent manual colour state in `tests/integration/test_splat_colour_wait.py`

### Implementation for User Story 2

- [ ] T022 [US2] Refactor pipeline colour branching for `ColourRestorationMode.OFF` in `src/reefs/cli.py`
- [ ] T023 [US2] Ensure SfM image-source selection uses raw images in off mode in `src/reefs/sfm/pipeline.py`
- [ ] T024 [US2] Ensure splat preflight blocks only manual incomplete state and never off mode in `src/reefs/preflight/splat.py`
- [ ] T025 [US2] Run `uv run pytest tests/integration/test_colour_disabled_pipeline.py tests/integration/test_sfm_recoloured_undistortion.py tests/integration/test_splat_colour_wait.py`

**Checkpoint**: User Story 2 is complete when off mode has no colour workflow side effects.

---

## Phase 5: User Story 3 - Run Automatic Gray-World Restoration (Priority: P2)

**Goal**: `mode: gray_world` creates complete full-resolution RGB restored outputs with gray-world strength `1.0`, records complete state, skips the GUI, and feeds restored images to undistortion.

**Independent Test**: Run gray-world apply/pipeline routes and verify output count, dimensions, RGB mode, state completion, no GUI launch, reuse/overwrite behaviour, and restored-image undistortion handoff.

### Tests for User Story 3

- [ ] T026 [P] [US3] Add gray-world full-resolution output tests in `tests/integration/test_colour_apply.py`
- [ ] T027 [P] [US3] Add gray-world CLI no-GUI behaviour tests in `tests/integration/test_colour_cli.py`
- [ ] T028 [P] [US3] Add gray-world reuse and overwrite tests in `tests/integration/test_colour_reuse.py`
- [ ] T029 [P] [US3] Add gray-world restored-image SfM handoff tests in `tests/integration/test_sfm_recoloured_undistortion.py`
- [ ] T030 [P] [US3] Add gray-world splat preflight completion tests in `tests/integration/test_splat_colour_wait.py`

### Implementation for User Story 3

- [ ] T031 [US3] Add an automatic gray-world apply helper using `ColourParameterSet(gray_world=1.0)` in `src/reefs/colour/pipeline.py`
- [ ] T032 [US3] Record gray-world mode, overwrite, output validation, and completion metadata in `src/reefs/colour/state.py` and `src/reefs/colour/pipeline.py`
- [ ] T033 [US3] Integrate gray-world mode into pipeline and `colour apply` routes without opening the GUI in `src/reefs/cli.py`
- [ ] T034 [US3] Enforce same-run compatible reuse when `overwrite` is false and explicit regeneration when true in `src/reefs/colour/pipeline.py`
- [ ] T035 [US3] Update SfM preflight and pipeline handoff to require completed gray-world outputs before using restored images in `src/reefs/preflight/sfm.py` and `src/reefs/sfm/pipeline.py`
- [ ] T036 [US3] Run `uv run pytest tests/integration/test_colour_apply.py tests/integration/test_colour_cli.py tests/integration/test_colour_reuse.py tests/integration/test_sfm_recoloured_undistortion.py tests/integration/test_splat_colour_wait.py`

**Checkpoint**: User Story 3 is complete when gray-world can run unattended and feed restored images downstream.

---

## Phase 6: User Story 4 - Continue Manual Colour Workflow (Priority: P3)

**Goal**: `mode: manual` preserves GUI open/resume/apply behaviour, active-session blocking, and same-run reuse/overwrite semantics.

**Independent Test**: Run manual open, resume, apply, complete-output reuse, overwrite, and splat-blocking regression tests.

### Tests for User Story 4

- [ ] T037 [P] [US4] Update manual colour CLI regression tests in `tests/integration/test_colour_cli.py`
- [ ] T038 [P] [US4] Update manual apply and output tests in `tests/integration/test_colour_apply.py` and `tests/integration/test_colour_outputs.py`
- [ ] T039 [P] [US4] Update manual pipeline resume and reuse tests in `tests/integration/test_colour_pipeline_resume.py` and `tests/integration/test_colour_reuse.py`
- [ ] T040 [P] [US4] Update manual splat-blocking tests in `tests/integration/test_splat_colour_wait.py`

### Implementation for User Story 4

- [ ] T041 [US4] Gate `colour open` so it is meaningful only for manual mode in `src/reefs/cli.py`
- [ ] T042 [US4] Preserve manual GUI launch/resume using `colour_restoration.start_sfm_immediately` in `src/reefs/cli.py`
- [ ] T043 [US4] Apply `colour_restoration.overwrite` to manual apply/reuse paths in `src/reefs/colour/pipeline.py`
- [ ] T044 [US4] Keep active/incomplete manual state blocking for splat preflight in `src/reefs/preflight/splat.py`
- [ ] T045 [US4] Run `uv run pytest tests/integration/test_colour_cli.py tests/integration/test_colour_apply.py tests/integration/test_colour_outputs.py tests/integration/test_colour_pipeline_resume.py tests/integration/test_colour_reuse.py tests/integration/test_splat_colour_wait.py`

**Checkpoint**: User Story 4 is complete when existing manual behaviour works through the new mode block.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, contract consistency, and full regression verification.

- [ ] T046 [P] Update README colour restoration mode documentation and command guidance in `README.MD`
- [ ] T047 [P] Update Spec Kit contracts and quickstart examples in `specs/011-colour-restoration-modes/contracts/` and `specs/011-colour-restoration-modes/quickstart.md`
- [ ] T048 [P] Verify unsupported `recolour_images` runtime references are removed while migration-error docs/tests remain intentional in `src/`, `tests/`, `configs/`, `README.MD`, and `specs/`
- [ ] T049 [P] Verify legacy `project.start_sfm_immediately` runtime references are removed while top-level `colour_restoration.start_sfm_immediately` docs/tests remain intentional in `src/`, `tests/`, `configs/`, `README.MD`, and `specs/`
- [ ] T050 Run focused colour/config/SfM handoff regression tests with `uv run pytest tests/unit/test_config_loader.py tests/unit/test_config_models.py tests/integration/test_colour_apply.py tests/integration/test_colour_cli.py tests/integration/test_colour_reuse.py tests/integration/test_sfm_recoloured_undistortion.py tests/integration/test_splat_colour_wait.py`
- [ ] T051 Run full regression suite with `uv run pytest tests`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational; MVP for config migration.
- **User Story 2 (Phase 4)**: Depends on User Story 1 config model.
- **User Story 3 (Phase 5)**: Depends on User Story 1 config model and shared colour state changes.
- **User Story 4 (Phase 6)**: Depends on User Story 1 config model and shared colour state changes.
- **Polish (Phase 7)**: Depends on implemented user stories.

### User Story Dependencies

- **US1**: Required first because all runtime modes depend on the new typed config.
- **US2**: Can start after US1 and is independent of automatic/manual output generation.
- **US3**: Can start after US1 and foundational state metadata.
- **US4**: Can start after US1 and foundational state metadata; may proceed in parallel with US3 if edits avoid the same files.

### Parallel Opportunities

- T002 and T003 can run in parallel.
- T010-T013 can run in parallel.
- T019-T021 can run in parallel.
- T026-T030 can run in parallel.
- T037-T040 can run in parallel.
- T046-T049 can run in parallel after implementation.

---

## Parallel Example: User Story 3

```bash
Task: "T026 Add gray-world full-resolution output tests in tests/integration/test_colour_apply.py"
Task: "T027 Add gray-world CLI no-GUI behaviour tests in tests/integration/test_colour_cli.py"
Task: "T028 Add gray-world reuse and overwrite tests in tests/integration/test_colour_reuse.py"
Task: "T029 Add gray-world restored-image SfM handoff tests in tests/integration/test_sfm_recoloured_undistortion.py"
Task: "T030 Add gray-world splat preflight completion tests in tests/integration/test_splat_colour_wait.py"
```

---

## Implementation Strategy

### MVP First

1. Complete Setup and Foundational tasks.
2. Complete User Story 1.
3. Validate config migration independently with T018.

### Incremental Delivery

1. Deliver US1 for safe config loading and explicit migration failures.
2. Deliver US2 for raw-image off mode.
3. Deliver US3 for unattended gray-world mode.
4. Deliver US4 for manual regression compatibility.
5. Complete Polish and full regression.

### Stop Points

- Stop after T018 if config migration tests fail.
- Stop after T025 if off mode creates colour state or uses restored images.
- Stop after T036 if gray-world outputs are incomplete or GUI opens.
- Stop after T045 if manual active-session blocking or reuse regresses.
