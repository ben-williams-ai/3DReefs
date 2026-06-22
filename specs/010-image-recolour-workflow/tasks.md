# Tasks: Optional Image Recolour Workflow

**Input**: Design documents from `specs/010-image-recolour-workflow/`
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Included because `spec.md` explicitly requires focused tests for ordering, keyframes, state, correction outputs, undistortion handoff, reopening/resume behaviour, standalone colour restoration, and failure/waiting behaviour.

**Organisation**: Tasks are grouped by user story so each story can be implemented and tested independently after the shared foundation is complete.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare dependencies, package structure, and configuration surfaces used by later stories.

- [x] T001 Add direct runtime dependencies for `PySide6`, `numpy`, `Pillow`, and `torch` in `pyproject.toml`
- [x] T002 Create the colour package skeleton with `src/reefs/colour/__init__.py`, `src/reefs/colour/filters.py`, `src/reefs/colour/interpolation.py`, `src/reefs/colour/ordering.py`, `src/reefs/colour/pipeline.py`, `src/reefs/colour/state.py`, and `src/reefs/colour/gui.py`
- [x] T003 Add `project.start_sfm_immediately` with default `true` to `ProjectConfig` in `src/reefs/config/models.py`
- [x] T004 Document `project.recolour_images` and `project.start_sfm_immediately` defaults in `configs/example.yml`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build shared primitives that all user stories rely on.

**Critical**: No user story work should begin until this phase is complete.

- [x] T005 [P] Define typed image sequence, image item, camera group, keyframe, parameter set, and restoration state models in `src/reefs/colour/state.py`
- [x] T006 [P] Implement atomic JSON load/save, schema version handling, timestamp updates, and status transitions for colour state in `src/reefs/colour/state.py`
- [x] T007 [P] Implement neutral `ColourParameterSet` defaults and validation for all Wildflow colour parameters in `src/reefs/colour/filters.py`
- [x] T008 [P] Implement metadata-first and natural-relative-path image ordering helpers in `src/reefs/colour/ordering.py`
- [x] T009 [P] Implement keyframe selection and rebuild helpers that centre default keyframes within bins in `src/reefs/colour/interpolation.py`
- [x] T010 [P] Implement per-parameter linear interpolation, before-first and after-last clamping, single-edited-keyframe handling, and no-edited-keyframe failure in `src/reefs/colour/interpolation.py`
- [x] T011 [P] Implement corrected image tree validation helpers for mirrored paths, exact dimensions, RGB output, and missing/extra image detection in `src/reefs/colour/pipeline.py`
- [x] T012 [P] Add shared ordering unit tests for metadata fallback, natural sorting, and multi-camera grouping in `tests/unit/test_colour_ordering.py`
- [x] T013 [P] Add keyframe and interpolation unit tests for centred defaults, rebuild preservation, clamping, single-keyframe application, and no-edited-keyframe failure in `tests/unit/test_colour_interpolation.py`
- [x] T014 [P] Add colour state unit tests for save/load, status transitions, active session flags, and overwrite-confirmation state in `tests/unit/test_colour_state.py`
- [x] T015 Add a colour orchestration service that builds run paths, loads image sequences, initialises/restores state, and exposes pipeline-safe status checks in `src/reefs/colour/pipeline.py`
- [x] T016 [P] Add preflight overwrite-decision tests for existing or partial `recoloured_images/` outputs in `tests/integration/test_colour_preflight_overwrite.py`
- [x] T017 Implement preflight detection of existing or partial `recoloured_images/` outputs and require explicit overwrite/resume/skip intent before requested pipeline or standalone colour steps start in `src/reefs/colour/pipeline.py`

**Checkpoint**: Shared colour domain logic, ordering, state persistence, and validation are ready for story work.

---

## Phase 3: User Story 1 - Run The Existing Pipeline Unchanged By Default (Priority: P1)

**Goal**: Preserve current behaviour when colour restoration is disabled.

**Independent Test**: Run the pipeline with `project.recolour_images: false` and verify no GUI opens, no corrected image root is required, and existing raw-image handoff paths remain in use.

### Tests for User Story 1

- [x] T018 [P] [US1] Add config default tests for disabled `project.recolour_images` and enabled `project.start_sfm_immediately` in `tests/unit/test_config_models.py`
- [x] T019 [P] [US1] Add integration coverage proving disabled colour restoration keeps raw-image preflight, SfM, undistortion, patching, and LFS handoff behaviour in `tests/integration/test_colour_disabled_pipeline.py`

### Implementation for User Story 1

- [x] T020 [US1] Wire `project.start_sfm_immediately` through config loading without changing disabled colour behaviour in `src/reefs/config/models.py`
- [x] T021 [US1] Keep colour orchestration bypassed when `project.recolour_images` is false in `src/reefs/cli.py`
- [x] T022 [US1] Ensure preflight does not require or create `recoloured_images/` when colour restoration is disabled in `src/reefs/preflight/images.py`
- [x] T023 [US1] Preserve existing raw-image undistortion source selection for disabled colour runs in `src/reefs/sfm/pipeline.py`

**Checkpoint**: User Story 1 is independently functional and testable as the backwards-compatible MVP.

---

## Phase 4: User Story 2 - Recolour Images While Preserving Raw SfM Geometry (Priority: P1)

**Goal**: Use raw images for SfM geometry while using corrected full-resolution images for the standard downstream undistorted handoff.

**Independent Test**: Enable colour restoration, complete correction, and verify SfM reads `raw_images/` while `sfm/undistorted/images` derives from `recoloured_images/` with a matching sparse handoff.

### Tests for User Story 2

- [x] T024 [P] [US2] Add filter-order and neutral-default unit tests against the provided Wildflow behaviour in `tests/unit/test_colour_filters.py`
- [x] T025 [P] [US2] Add corrected output structure and dimension tests in `tests/integration/test_colour_outputs.py`
- [x] T026 [P] [US2] Extend corrected-image undistortion handoff tests for raw SfM geometry plus corrected undistorted images in `tests/integration/test_sfm_recoloured_undistortion.py`
- [x] T027 [P] [US2] Add colour acceleration detection and fallback tests in `tests/unit/test_colour_filters.py`

### Implementation for User Story 2

- [x] T028 [US2] Implement the Wildflow-source colour filter order in `src/reefs/colour/filters.py`
- [x] T029 [US2] Detect and report the selected colour processing device while completing correctly without acceleration in `src/reefs/colour/filters.py`
- [x] T030 [US2] Implement full-resolution image loading, RGB conversion, extension preservation where possible, and high-quality lossy saving in `src/reefs/colour/pipeline.py`
- [x] T031 [US2] Implement batch correction from raw images to the mirrored `recoloured_images/` tree in `src/reefs/colour/pipeline.py`
- [x] T032 [US2] Keep SfM feature extraction and reconstruction image paths fixed to raw images in `src/reefs/sfm/pipeline.py`
- [x] T033 [US2] Use corrected images only for the final standard COLMAP undistortion handoff when colour state is complete in `src/reefs/sfm/pipeline.py`
- [x] T034 [US2] Validate standard `sfm/undistorted/images` and `sfm/undistorted/sparse` handoff consistency for corrected runs in `src/reefs/sfm/validation.py`

**Checkpoint**: User Story 2 is independently functional and testable with completed corrected images.

---

## Phase 5: User Story 3 - Tune And Resume Keyframe Colour Edits (Priority: P2)

**Goal**: Provide a PySide6 GUI that saves keyframe edits continuously and resumes interrupted work.

**Independent Test**: Open the GUI, edit keyframes, close or simulate a failure, reopen the same run, and verify keyframes, values, status, and current position are restored.

### Tests for User Story 3

- [x] T035 [P] [US3] Add GUI-state controller tests for edit/save/delete/rebuild actions in `tests/unit/test_colour_gui_state.py`
- [x] T036 [P] [US3] Add resume-after-interruption integration tests in `tests/integration/test_colour_pipeline_resume.py`

### Implementation for User Story 3

- [x] T037 [US3] Implement GUI controller methods that update colour state immediately after keyframe creation, edit save, overwrite, deletion, rebuild, mode change, and session state changes in `src/reefs/colour/gui.py`
- [x] T038 [US3] Implement raw and corrected preview rendering from full source images while keeping preview data separate from final outputs in `src/reefs/colour/gui.py`
- [x] T039 [US3] Add slider and exact numeric entry controls for every colour parameter in `src/reefs/colour/gui.py`
- [x] T040 [US3] Add previous/next navigation, direct index entry, and a clickable scrollable keyframe list in `src/reefs/colour/gui.py`
- [x] T041 [US3] Add keyframe list rows with order, camera folder, dataset position, per-camera position, filename context, deletion control, edit status or saved values, and raw thumbnail in `src/reefs/colour/gui.py`
- [x] T042 [US3] Implement close handling for cancel, skip colour restoration, and return to editing in `src/reefs/colour/gui.py`
- [x] T043 [US3] Add GUI launch and GUI-open failure handling in `src/reefs/colour/pipeline.py`

**Checkpoint**: User Story 3 is independently functional and testable with saved resumable GUI state.

---

## Phase 6: User Story 4 - Apply Interpolated Corrections To The Dataset (Priority: P2)

**Goal**: Apply saved keyframe parameters across the ordered image set to produce a complete corrected image tree.

**Independent Test**: Save edited keyframes, apply correction, and verify every expected output image exists with matching path, filename, RGB mode, and dimensions.

### Tests for User Story 4

- [x] T044 [P] [US4] Add full-dataset interpolation and apply integration tests in `tests/integration/test_colour_apply.py`
- [x] T045 [P] [US4] Add output RGB, dimensions, extension, and JPEG quality regression tests in `tests/integration/test_colour_outputs.py`

### Implementation for User Story 4

- [x] T046 [US4] Connect interpolation results to batch image correction for global and per-camera scopes in `src/reefs/colour/pipeline.py`
- [x] T047 [US4] Add unedited-keyframe apply warning data and no-edited-keyframe failure behaviour in `src/reefs/colour/pipeline.py`
- [x] T048 [US4] Record interpolation inputs and output validation results in colour state after apply in `src/reefs/colour/state.py`
- [x] T049 [US4] Add GUI apply action with confirmation, progress callback, completion state, and failure state updates in `src/reefs/colour/gui.py`

**Checkpoint**: User Story 4 is independently functional and testable with complete corrected image outputs.

---

## Phase 7: User Story 5 - Use Robust Dataset Image Ordering (Priority: P2)

**Goal**: Route all sequence-sensitive operations through one ordering strategy.

**Independent Test**: Use representative filename and multi-camera layouts to verify capture order or natural path order is used consistently by reconstruction lists, patch selection, LFS handoff, and colour interpolation.

### Tests for User Story 5

- [x] T050 [P] [US5] Extend image layout tests for natural sorting and metadata fallback in `tests/unit/test_image_layout.py`
- [x] T051 [P] [US5] Add ordering audit integration tests for SfM image lists, patch selection, LFS handoff, and colour interpolation in `tests/integration/test_ordering_audit.py`

### Implementation for User Story 5

- [x] T052 [US5] Replace ad hoc image sorting in preflight layout detection with shared ordering helpers in `src/reefs/preflight/images.py`
- [x] T053 [US5] Use shared ordering for SfM image list generation and reconstruction-sensitive image comparisons in `src/reefs/sfm/pipeline.py`
- [x] T054 [US5] Use shared ordering for patch image selection in `src/reefs/splat/pipeline.py`
- [x] T055 [US5] Use shared ordering for LFS handoff wherever images are ordered in `src/reefs/splat/validation.py`
- [x] T056 [US5] Record ordering method and warnings in colour restoration state in `src/reefs/colour/state.py`

**Checkpoint**: User Story 5 is independently functional and testable across all ordering-sensitive paths.

---

## Phase 8: User Story 6 - Review And Continue Colour Corrections (Priority: P2)

**Goal**: Let users inspect corrected outputs, reopen the GUI, continue editing, and keep splatting blocked while a colour session is active.

**Independent Test**: Complete one correction pass, reopen the same run, make new edits, reapply with overwrite warning, and verify splatting waits during the reopened session.

### Tests for User Story 6

- [x] T057 [P] [US6] Add CLI contract tests for `colour open` and `colour apply` commands in `tests/integration/test_colour_cli.py`
- [x] T058 [P] [US6] Add reopened GUI waiting integration tests in `tests/integration/test_splat_colour_wait.py`
- [x] T059 [P] [US6] Add integration tests for `project.start_sfm_immediately: true` background SfM and `false` SfM-waits behaviour in `tests/integration/test_colour_pipeline_resume.py`

### Implementation for User Story 6

- [x] T060 [US6] Convert `src/reefs/cli.py` to expose the existing pipeline command plus `colour open` and `colour apply` subcommands from the same `uv run main.py` entrypoint
- [x] T061 [US6] Implement pipeline orchestration for `project.start_sfm_immediately` so raw-image SfM runs in the background when enabled and waits for complete or skipped colour state when disabled in `src/reefs/cli.py`
- [x] T062 [US6] Implement `colour open` to load or initialise run colour state and reopen the GUI with saved keyframes, mode, ordering, and paths in `src/reefs/cli.py`
- [x] T063 [US6] Implement `colour apply` to run the standalone correction workflow without SfM, patching, or splatting in `src/reefs/cli.py`
- [x] T064 [US6] Mark `active_session` true while GUI or standalone apply is active and false on safe exit in `src/reefs/colour/pipeline.py`
- [x] T065 [US6] Add splat wait gate for active, applying, incomplete, or failed colour state in `src/reefs/splat/pipeline.py`
- [x] T066 [US6] Add explicit overwrite warning and confirmation before replacing existing `recoloured_images/` outputs in `src/reefs/colour/gui.py`

**Checkpoint**: User Story 6 is independently functional and testable for review, reopen, standalone, and wait behaviour.

---

## Phase 9: User Story 7 - Fail Safely And Resume Work (Priority: P2)

**Goal**: Preserve saved work, report clear failures, and prevent incomplete corrected outputs from reaching splatting.

**Independent Test**: Simulate GUI launch failure, pipeline failure during edits, partial apply failure, and rerun; verify state is preserved and downstream processing is blocked or resumed correctly.

### Tests for User Story 7

- [x] T067 [P] [US7] Add GUI-open failure and early pipeline failure tests in `tests/integration/test_colour_failure_paths.py`
- [x] T068 [P] [US7] Add partial apply failure and incomplete-output blocking tests in `tests/integration/test_splat_colour_wait.py`

### Implementation for User Story 7

- [x] T069 [US7] Persist failure details including failing image and exception message in colour state from `src/reefs/colour/pipeline.py`
- [x] T070 [US7] Prevent corrected undistortion and splatting from consuming partial corrected image trees in `src/reefs/sfm/validation.py`
- [x] T071 [US7] Resume incomplete colour restoration state by default for the same run in `src/reefs/colour/pipeline.py`
- [x] T072 [US7] Preserve GUI state and close or stop GUI work cleanly when another pipeline stage fails in `src/reefs/cli.py`
- [x] T073 [US7] Implement skip-state handling so skipped colour restoration uses normal raw-image handoff behaviour in `src/reefs/sfm/pipeline.py`

**Checkpoint**: User Story 7 is independently functional and testable for failure, resume, skip, and blocking behaviour.

---

## Phase 10: User Story 8 - Correct Multi-Camera Datasets Deliberately (Priority: P2)

**Goal**: Support both dataset-wide edits and separate per-camera edits without breaking folder or camera identities.

**Independent Test**: Run colour restoration on multiple camera folders in global and per-camera modes and verify folder paths, identities, interpolation scopes, and saved edits are preserved.

### Tests for User Story 8

- [x] T074 [P] [US8] Add per-camera mode unit tests for grouping, keyframe scopes, and mode switching in `tests/unit/test_colour_interpolation.py`
- [x] T075 [P] [US8] Add multi-camera corrected output integration tests in `tests/integration/test_colour_multicamera.py`

### Implementation for User Story 8

- [x] T076 [US8] Implement global and per-camera keyframe sequence construction in `src/reefs/colour/interpolation.py`
- [x] T077 [US8] Preserve saved edits across global/per-camera mode changes when referenced images remain valid in `src/reefs/colour/state.py`
- [x] T078 [US8] Add separate-by-camera GUI mode controls and rebuild behaviour in `src/reefs/colour/gui.py`
- [x] T079 [US8] Ensure batch correction preserves camera folders and never mixes image identities across camera groups in `src/reefs/colour/pipeline.py`

**Checkpoint**: User Story 8 is independently functional and testable for single-camera and multi-camera correction.

---

## Phase 11: User Story 9 - Make Informed Apply And Exit Decisions (Priority: P3)

**Goal**: Provide clear prompts, counts, progress, and completion/skip/cancel states.

**Independent Test**: Exercise apply with edited and unedited keyframes, cancel apply, close before completion, complete correction, and verify prompt text, counts, choices, progress, and saved status.

### Tests for User Story 9

- [x] T080 [P] [US9] Add prompt text and count unit tests for apply and close decisions in `tests/unit/test_colour_gui_prompts.py`
- [x] T081 [P] [US9] Add end-to-end prompt path tests for apply, cancel, skip, and completion in `tests/integration/test_colour_cli.py`

### Implementation for User Story 9

- [x] T082 [US9] Implement required apply confirmation prompts with unedited keyframe count, total image count, and edited keyframe count in `src/reefs/colour/gui.py`
- [x] T083 [US9] Implement required close choices and saved statuses for cancel, skip, and return-to-editing in `src/reefs/colour/gui.py`
- [x] T084 [US9] Emit full-dataset progress counts to GUI and terminal/log output during correction in `src/reefs/colour/pipeline.py`
- [x] T085 [US9] Display completion messaging that explains whether SfM is already running or will start after colour completion in `src/reefs/colour/gui.py`

**Checkpoint**: User Story 9 is independently functional and testable for informed prompts and progress feedback.

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, examples, and full verification across the completed feature.

- [x] T086 [P] Update `README.MD` with colour restoration workflow, background SfM behaviour, corrected-output review, reopen command, standalone command, splatting wait behaviour, and overwrite warning
- [x] T087 [P] Manually open the colour GUI after implementation, inspect the minimum supported window size, and record verification that controls do not overlap and navigation remains usable in `specs/010-image-recolour-workflow/quickstart.md`
- [x] T088 [P] Update dataset config examples under `configs/datasets/` to show explicit `project.recolour_images` and `project.start_sfm_immediately` choices where appropriate
- [x] T089 [P] Update `docs/decisions.md` with the colour restoration architecture, state location, overwrite policy, and standard handoff decision
- [x] T090 Run focused unit tests with `uv run pytest tests/unit/test_config_models.py tests/unit/test_colour_ordering.py tests/unit/test_colour_interpolation.py tests/unit/test_colour_state.py tests/unit/test_colour_filters.py tests/unit/test_colour_gui_state.py tests/unit/test_colour_gui_prompts.py`
- [x] T091 Run focused integration tests with `uv run pytest tests/integration/test_colour_cli.py tests/integration/test_colour_pipeline_resume.py tests/integration/test_sfm_recoloured_undistortion.py tests/integration/test_splat_colour_wait.py tests/integration/test_colour_outputs.py tests/integration/test_colour_multicamera.py tests/integration/test_colour_disabled_pipeline.py tests/integration/test_ordering_audit.py tests/integration/test_colour_failure_paths.py tests/integration/test_colour_preflight_overwrite.py`
- [x] T092 Run the full test suite under `tests/` with `uv run pytest tests`
- [x] T093 Validate the quickstart workflow from `specs/010-image-recolour-workflow/quickstart.md` against the implemented CLI commands
- [x] T094 [P] Add tests for adopting complete existing `recoloured_images/`, rejecting missing/dimension/mode-invalid corrected images, and keeping `colour apply --overwrite` replacement behaviour in `tests/integration/test_colour_reuse.py`, `tests/integration/test_colour_cli.py`, and `tests/integration/test_sfm_recoloured_undistortion.py`
- [x] T095 Implement complete existing `recoloured_images/` adoption and run-local complete state persistence in `src/reefs/colour/pipeline.py`
- [x] T096 Update main pipeline and standalone `colour apply` orchestration to reuse complete corrected outputs by default, print the reuse message, and continue requiring `--overwrite` for intentional replacement in `src/reefs/cli.py`
- [x] T097 Update `spec.md`, `data-model.md`, `quickstart.md`, and `README.MD` with the correct-once, reuse-many-experiments workflow
- [x] T098 Re-run focused colour/CLI/SfM handoff tests and the full `uv run pytest tests` suite after reuse implementation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: No dependencies; starts immediately.
- **Phase 2 Foundational**: Depends on Phase 1 and blocks all user stories.
- **US1 and US2 (P1)**: Depend on Phase 2; implement first for MVP and core feature correctness.
- **US3 to US8 (P2)**: Depend on Phase 2; can proceed after P1 paths are stable, with US4 depending on US3 GUI state and shared interpolation.
- **US9 (P3)**: Depends on US3, US4, US6, and US7 because it polishes prompts around their flows.
- **Phase 12 Polish**: Depends on the desired user stories being complete.

### User Story Dependencies

- **US1**: Foundation only; MVP compatibility slice.
- **US2**: Foundation plus US1 disabled-path safety.
- **US3**: Foundation; GUI and state can be developed alongside US2 after core models exist.
- **US4**: Foundation plus US3 state/edit flows.
- **US5**: Foundation; should be completed before broad integration testing because it affects many paths.
- **US6**: Foundation plus US3/US4 apply state.
- **US7**: Foundation plus US3/US4/US6 failure and wait states.
- **US8**: Foundation plus US4 interpolation and output application.
- **US9**: US3/US4/US6/US7 prompt surfaces.

### Within Each User Story

- Tests should be written first and fail before implementation.
- Models and pure helpers before services.
- Services before CLI, GUI, or pipeline orchestration.
- Story checkpoints should pass before moving to the next priority group.

---

## Parallel Opportunities

- Setup task T004 can run after T003 while T001 and T002 are in progress if dependency resolution is known.
- Foundational pure-module tasks T005-T016 can run in parallel across different files.
- US1 test tasks T018-T019 can run in parallel before implementation.
- US2 test tasks T024-T027 can run in parallel before implementation.
- US3 test tasks T035-T036 can run in parallel before implementation.
- US4 test tasks T044-T045 can run in parallel before implementation.
- US5 test tasks T050-T051 can run in parallel before implementation.
- US6 test tasks T058-T060 can run in parallel before implementation.
- US7 test tasks T068-T069 can run in parallel before implementation.
- US8 test tasks T075-T076 can run in parallel before implementation.
- US9 test tasks T081-T082 can run in parallel before implementation.
- Documentation and manual verification tasks T086-T089 can run in parallel after relevant behaviour is implemented.

## Parallel Example: User Story 2

```text
Task: "T024 [P] [US2] Add filter-order and neutral-default unit tests against the provided Wildflow behaviour in tests/unit/test_colour_filters.py"
Task: "T025 [P] [US2] Add corrected output structure and dimension tests in tests/integration/test_colour_outputs.py"
Task: "T026 [P] [US2] Extend corrected-image undistortion handoff tests for raw SfM geometry plus corrected undistorted images in tests/integration/test_sfm_recoloured_undistortion.py"
Task: "T027 [P] [US2] Add colour acceleration detection and fallback tests in tests/unit/test_colour_filters.py"
```

## Parallel Example: User Story 6

```text
Task: "T058 [P] [US6] Add CLI contract tests for colour open and colour apply commands in tests/integration/test_colour_cli.py"
Task: "T059 [P] [US6] Add reopened GUI waiting integration tests in tests/integration/test_splat_colour_wait.py"
Task: "T060 [P] [US6] Add integration tests for project.start_sfm_immediately true/false behaviour in tests/integration/test_colour_pipeline_resume.py"
```

---

## Implementation Strategy

### MVP First

1. Complete Phase 1 setup.
2. Complete Phase 2 foundation.
3. Complete US1 to prove disabled colour restoration preserves existing behaviour.
4. Complete US2 to prove raw SfM plus corrected standard handoff works.
5. Stop and validate P1 before expanding GUI and resume flows.

### Incremental Delivery

1. Deliver US1 and US2 as the safety and core correctness slice.
2. Add US3 and US4 for GUI editing and full-dataset correction.
3. Add US5 to standardise ordering across the pipeline.
4. Add US6 and US7 for reopen, standalone, wait, failure, and resume behaviour.
5. Add US8 and US9 for multi-camera polish and complete prompts.
6. Finish Phase 12 documentation and verification.

### Validation Strategy

1. Run story-specific tests at each checkpoint.
2. Run focused unit and integration commands in T090 and T091 before final full-suite validation.
3. Run `uv run pytest` after all desired stories are complete.
4. Validate `quickstart.md` manually against the implemented CLI behaviour.
