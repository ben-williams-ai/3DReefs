# Tasks: Splat Patching And Training

**Input**: Design documents from `/specs/003-splat-patching-training/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included because the feature plan requires unit and integration tests for patching, outlier filtering, LFS command/status handling, resume decisions, and smoke validation on local data.

**Organization**: Tasks are grouped by user story so patch generation can land as the MVP, then outlier filtering, training, and existing-output handling can be added as independent increments. Up-front validation and existing-output guards are foundational because no requested splat stage should start before all prompt/overwrite/reuse decisions that can be known have already been resolved.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files or depends only on completed earlier phases.
- **[Story]**: User story label from `spec.md`.
- Every task includes an exact file path.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add dependencies, module skeletons, and config surface needed by all Feature 3 stories.

- [ ] T001 Add `pycolmap` and `matplotlib` runtime dependencies to `pyproject.toml`
- [ ] T002 Refresh dependency lockfile with `uv lock`
- [ ] T003 [P] Create patching package skeleton files in `src/reefs/patches/__init__.py`, `src/reefs/patches/artefacts.py`, `src/reefs/patches/bounds.py`, `src/reefs/patches/export.py`, `src/reefs/patches/outliers.py`, `src/reefs/patches/selection.py`, and `src/reefs/patches/validation.py`
- [ ] T004 [P] Create splat orchestration package skeleton files in `src/reefs/splat/__init__.py`, `src/reefs/splat/pipeline.py`, `src/reefs/splat/resume.py`, and `src/reefs/splat/validation.py`
- [ ] T005 [P] Create LFS package skeleton files in `src/reefs/lfs/__init__.py`, `src/reefs/lfs/commands.py`, `src/reefs/lfs/runner.py`, and `src/reefs/lfs/status.py`
- [ ] T006 [P] Create splat diagnostics skeleton files in `src/reefs/diagnostics/patch_plots.py` and `src/reefs/diagnostics/training.py`
- [ ] T007 [P] Create splat preflight skeleton in `src/reefs/preflight/splat.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared config, stage routing, sparse-model IO, and run-record helpers that all user stories need.

**Critical**: No user story implementation should begin until this phase is complete.

- [ ] T008 Add typed `advanced.splat.outlier_filter`, `advanced.splat.patching`, and `advanced.splat.train` models in `src/reefs/config/models.py`
- [ ] T009 Update `configs/example.yml` with complete Feature 3 advanced splat settings and comments
- [ ] T010 Update `configs/test.yml` and `configs/datasets/dataset_01.yml` through `configs/datasets/dataset_05.yml` with Feature 3 splat settings inherited from `configs/example.yml`
- [ ] T011 [P] Add splat config validation tests in `tests/unit/test_splat_config.py`
- [ ] T012 [P] Add pycolmap availability checks and source sparse fixture helpers in `tests/conftest.py`
- [ ] T013 Implement COLMAP sparse model adapter helpers in `src/reefs/patches/artefacts.py`
- [ ] T014 Implement splat source reconstruction validation in `src/reefs/splat/validation.py`
- [ ] T015 Add source reconstruction validation tests in `tests/unit/test_splat_source_validation.py`
- [ ] T016 Extend CLI step expansion and routing for `splat`, `splat.preflight`, `splat.outlier_filter`, `splat.patch`, and `splat.train` in `src/reefs/cli.py`
- [ ] T017 Implement splat preflight orchestration in `src/reefs/preflight/splat.py`, including earliest possible `pycolmap` validation and LFS validation when training is requested
- [ ] T018 Integrate dotted splat stage names and durable run-record updates in `src/reefs/splat/pipeline.py`
- [ ] T019 Add mocked CLI preflight tests for missing SfM outputs, missing `pycolmap`, and missing LFS when training is requested in `tests/integration/test_splat_mocked_failures.py`
- [ ] T020 Implement a foundational existing-output guard in `src/reefs/splat/resume.py` and `src/reefs/preflight/splat.py` that detects prior patch/training outputs for all requested splat stages and fails, prompts, resumes, or overwrites before any outlier filtering, patching, or LFS work starts

**Checkpoint**: Config, source validation, CLI routing, and run-record plumbing are ready for story work.

---

## Phase 3: User Story 1 - Create Trainable Reef Patches (Priority: P1) MVP

**Goal**: Create valid patch datasets from completed Feature 2 undistorted SfM outputs, with selected images, sparse data, metadata, and diagnostics.

**Independent Test**: Run `uv run main.py --config configs/test.yml --steps splat.patch --advanced.splat.outlier_filter.enabled false --resume-policy overwrite` on the completed test dataset SfM output and inspect patch folders without launching LFS.

### Tests for User Story 1

- [ ] T021 [P] [US1] Add patch bounds unit tests in `tests/unit/test_patch_bounds.py`
- [ ] T022 [P] [US1] Add view-based patch selection unit tests in `tests/unit/test_patch_selection.py`
- [ ] T023 [P] [US1] Add patch artefact export unit tests in `tests/unit/test_patch_export.py`
- [ ] T024 [P] [US1] Add patch diagnostics generation unit tests in `tests/unit/test_patch_diagnostics.py`
- [ ] T025 [US1] Add mocked patch generation integration test in `tests/integration/test_splat_mocked_success.py`

### Implementation for User Story 1

- [ ] T026 [P] [US1] Implement scene-relative patch anchor and bound generation in `src/reefs/patches/bounds.py`
- [ ] T027 [P] [US1] Implement view-based camera scoring and selection in `src/reefs/patches/selection.py`, using sparse-point visibility, projected coverage, boundary coverage, median depth, azimuth-sector balancing, and deterministic tie-breaking from the old `select_by_views` evidence
- [ ] T028 [US1] Implement patch metadata creation and validation in `src/reefs/patches/artefacts.py`
- [ ] T029 [US1] Implement pycolmap sparse subset export for selected patch cameras in `src/reefs/patches/export.py`
- [ ] T030 [US1] Implement selected image symlink creation in `src/reefs/patches/export.py`
- [ ] T031 [P] [US1] Implement patch coverage CSV and plot diagnostics in `src/reefs/diagnostics/patch_plots.py`
- [ ] T032 [US1] Implement patch-generation orchestration in `src/reefs/splat/pipeline.py`
- [ ] T033 [US1] Record patch manifest summaries and patching timings in `src/reefs/splat/pipeline.py`
- [ ] T034 [US1] Add invalid patch classification for missing points, missing selected images, too few images, and export failures in `src/reefs/patches/validation.py`
- [ ] T035 [US1] Run local test-dataset patch-generation smoke check using `data/test_dataset` and update `specs/003-splat-patching-training/quickstart.md` with the exact verified command

**Checkpoint**: Patch datasets can be generated and inspected without LFS training.

---

## Phase 4: User Story 2 - Audit And Filter Camera Pose Outliers (Priority: P2)

**Goal**: Detect obvious camera pose outliers, write a filtered reconstruction copy when safe, and stop before patching when proposed removals are ambiguous.

**Independent Test**: Run `uv run main.py --config configs/test.yml --steps splat.outlier_filter --advanced.splat.outlier_filter.dry_run true` and inspect the filter summary plus before/after diagnostics.

### Tests for User Story 2

- [ ] T036 [P] [US2] Add camera pose outlier scoring tests in `tests/unit/test_patch_outliers.py`
- [ ] T037 [P] [US2] Add ambiguous-removal blocking tests in `tests/unit/test_patch_outliers.py`
- [ ] T038 [P] [US2] Add outlier diagnostic plot tests in `tests/unit/test_outlier_diagnostics.py`
- [ ] T039 [US2] Add mocked outlier-filter integration tests in `tests/integration/test_splat_outlier_filter.py`

### Implementation for User Story 2

- [ ] T040 [P] [US2] Implement camera centre extraction and robust outlier scoring in `src/reefs/patches/outliers.py`
- [ ] T041 [US2] Implement max-removal-fraction ambiguity handling in `src/reefs/patches/outliers.py`
- [ ] T042 [US2] Implement filtered sparse reconstruction export in `src/reefs/patches/export.py`
- [ ] T043 [P] [US2] Implement before/after top and side camera pose diagnostics in `src/reefs/diagnostics/patch_plots.py`
- [ ] T044 [US2] Write `splat/outlier_filter/filter_summary.json` records in `src/reefs/splat/pipeline.py`
- [ ] T045 [US2] Integrate enabled, disabled, dry-run, no-removal, removal, and ambiguous states into `src/reefs/splat/pipeline.py`
- [ ] T046 [US2] Ensure patching uses the filtered reconstruction when filtering completes in `src/reefs/splat/pipeline.py`

**Checkpoint**: Outlier filtering is auditable and safely feeds patch generation.

---

## Phase 5: User Story 3 - Train Patch Splats In Batch (Priority: P3)

**Goal**: Train valid patch splats with LichtFeld Studio one patch at a time and record patch-level status, logs, timings, and artefacts.

**Independent Test**: Run `uv run main.py --config configs/test.yml --steps splat.train --advanced.splat.train.patch_ids "[p000]" --advanced.splat.train.num_iters 500` with mocked LFS first, then with local LFS when available.

### Tests for User Story 3

- [ ] T047 [P] [US3] Add LFS command construction tests in `tests/unit/test_lfs_commands.py`
- [ ] T048 [P] [US3] Add LFS progress parsing and status classification tests in `tests/unit/test_lfs_status.py`
- [ ] T049 [P] [US3] Add patch training selection tests for all patches and explicit patch IDs in `tests/unit/test_splat_training_selection.py`
- [ ] T050 [US3] Add mocked successful and partial LFS training integration tests in `tests/integration/test_splat_training_status.py`
- [ ] T051 [US3] Add mocked LFS failure integration test in `tests/integration/test_splat_mocked_failures.py`

### Implementation for User Story 3

- [ ] T052 [P] [US3] Implement LFS command builder in `src/reefs/lfs/commands.py`
- [ ] T053 [P] [US3] Implement LFS progress parser and status classifier in `src/reefs/lfs/status.py`
- [ ] T054 [US3] Implement LFS subprocess runner with streamed global and patch-local logs in `src/reefs/lfs/runner.py`
- [ ] T055 [US3] Implement temporary LFS dataset staging for one patch in `src/reefs/lfs/runner.py`
- [ ] T056 [US3] Implement patch selection for all patches and explicit patch IDs in `src/reefs/splat/pipeline.py`
- [ ] T057 [US3] Enforce exactly one active LFS training process in `src/reefs/splat/pipeline.py`
- [ ] T058 [US3] Record requested iterations, completed iterations, completion ratio, output artefact, return code, and duration in `src/reefs/splat/pipeline.py`
- [ ] T059 [US3] Implement invalid requested patch skipping with severe warnings before LFS starts in `src/reefs/splat/pipeline.py`
- [ ] T060 [US3] Implement explicit `advanced.splat.train.retrain_failed` handling in `src/reefs/splat/pipeline.py`
- [ ] T061 [US3] Write patch training manifest and timing updates through `src/reefs/runs/recorder.py` integration in `src/reefs/splat/pipeline.py`
- [ ] T062 [US3] Update `specs/003-splat-patching-training/quickstart.md` with the verified short-iteration training smoke command

**Checkpoint**: Valid patches train serially and every requested patch receives a structured status.

---

## Phase 6: User Story 4 - Resolve Existing Patch Outputs Up Front (Priority: P4)

**Goal**: Detect existing patching and training outputs, compare patch-affecting settings, and resolve reuse/overwrite/skip/stop decisions before any requested work starts.

**Independent Test**: Create valid patch outputs and partial training outputs, rerun `splat.patch` or `splat.train` with `--resume-policy resume`, `overwrite`, and `fail`, and confirm all decisions are recorded before any LFS process starts.

### Tests for User Story 4

- [ ] T063 [P] [US4] Add patch-affecting config diff tests in `tests/unit/test_patch_reuse.py`
- [ ] T064 [P] [US4] Add existing patch dataset validation tests in `tests/unit/test_patch_reuse.py`
- [ ] T065 [P] [US4] Add existing training output decision tests in `tests/unit/test_splat_resume.py`
- [ ] T066 [US4] Add integration tests for resume, overwrite, fail, and non-interactive missing-decision behaviour in `tests/integration/test_splat_partial_outputs.py`

### Implementation for User Story 4

- [ ] T067 [P] [US4] Implement patch-affecting config materialisation and comparison in `src/reefs/splat/resume.py`
- [ ] T068 [P] [US4] Implement existing patch validation and reuse decision helpers in `src/reefs/splat/resume.py`
- [ ] T069 [US4] Implement existing training-output detection and decision helpers in `src/reefs/splat/resume.py`
- [ ] T070 [US4] Integrate detailed up-front patch reuse and overwrite decisions into `src/reefs/splat/pipeline.py`
- [ ] T071 [US4] Integrate detailed up-front training reuse, retrain, skip, and stop decisions into `src/reefs/splat/pipeline.py`
- [ ] T072 [US4] Record patch reuse decisions, config differences, and skip reasons in `run_manifest.json` through `src/reefs/splat/pipeline.py`
- [ ] T073 [US4] Ensure non-interactive missing-decision paths fail before patching or LFS starts in `src/reefs/splat/pipeline.py`

**Checkpoint**: Existing patch/training outputs are handled up front and unattended runs do not pause mid-pipeline.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Validate docs, run smoke checks, and tidy behaviour across all Feature 3 stories.

- [ ] T074 [P] Update `README.MD` with Feature 3 commands, data prerequisites, and LFS training caveats
- [ ] T075 [P] Add Feature 3 decisions and known failure modes to `docs/decisions.md` and `docs/troubleshooting.md`
- [ ] T076 Run `uv run pytest tests/unit tests/integration` and record failures or fixes in `docs/troubleshooting.md`
- [ ] T077 Run mocked end-to-end `splat.patch` and `splat.train` integration checks using `configs/test.yml`
- [ ] T078 Review the US1 local test-dataset patch-generation smoke artefacts and record any issues in `docs/troubleshooting.md`
- [ ] T079 Run local short LFS training smoke check for one patch when LichtFeld Studio is available
- [ ] T080 Review `specs/003-splat-patching-training/checklists/patch-training-requirements.md` and check off resolved requirements-quality items
- [ ] T081 Run `speckit-analyze` for Feature 3 and resolve any spec/plan/tasks inconsistencies in `specs/003-splat-patching-training/`
- [ ] T082 Ensure public docs/configs contain no private absolute paths except ignored local configs in `.env`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: No dependencies.
- **Phase 2 Foundational**: Depends on Phase 1 and blocks all user stories.
- **US1 Patch Generation**: Depends on Phase 2. This is the MVP.
- **US2 Outlier Filtering**: Depends on Phase 2 and integrates with US1 patch source selection.
- **US3 LFS Training**: Depends on Phase 2 and valid patch datasets from US1.
- **US4 Existing Output Decisions**: Depends on Phase 2 and integrates with US1/US3 outputs.
- **Polish**: Depends on whichever user stories are implemented.

### User Story Dependencies

- **US1 (P1)**: Can be implemented after foundational work; independent test may disable outlier filtering.
- **US2 (P2)**: Can be implemented after foundational work; final full patch flow should combine US2 then US1.
- **US3 (P3)**: Requires valid patch datasets from US1.
- **US4 (P4)**: Detailed reuse behaviour requires patch/training artefact definitions from US1/US3, but the minimal existing-output guard in T020 is foundational and must exist before any runnable patching or training stage is implemented.

### Parallel Opportunities

- T003 through T007 can run in parallel after T001/T002.
- T011, T012, T015, and T019 can be developed in parallel with foundational implementation files once config interfaces are stable.
- US1 unit tests T021 through T024 can run in parallel.
- US2 unit tests T036 through T038 can run in parallel.
- US3 unit tests T047 through T049 can run in parallel.
- US4 unit tests T063 through T065 can run in parallel.

---

## Parallel Example: User Story 1

```text
Task: "T021 Add patch bounds unit tests in tests/unit/test_patch_bounds.py"
Task: "T022 Add view-based patch selection unit tests in tests/unit/test_patch_selection.py"
Task: "T023 Add patch artefact export unit tests in tests/unit/test_patch_export.py"
Task: "T024 Add patch diagnostics generation unit tests in tests/unit/test_patch_diagnostics.py"
```

## Parallel Example: User Story 3

```text
Task: "T047 Add LFS command construction tests in tests/unit/test_lfs_commands.py"
Task: "T048 Add LFS progress parsing and status classification tests in tests/unit/test_lfs_status.py"
Task: "T049 Add patch training selection tests for all patches and explicit patch IDs in tests/unit/test_splat_training_selection.py"
```

---

## Implementation Strategy

### MVP First

1. Complete Phase 1 setup.
2. Complete Phase 2 foundational config, source validation, and CLI routing.
3. Complete US1 patch generation with outlier filtering disabled for the first independent smoke test.
4. Validate patch folders, metadata, sparse export, selected images, and diagnostics.

### Incremental Delivery

1. Add US1 patch generation and validate on `data/test_dataset`.
2. Add US2 outlier filtering and validate no-removal, removal, dry-run, and ambiguous cases.
3. Add US3 LFS training with mocked LFS first, then one short local LFS smoke run.
4. Add US4 existing-output decisions and rerun resume/overwrite/fail scenarios.
5. Run Feature 3 analysis and checklist review before considering the feature complete.

### Validation Notes

- Tests should be written before implementation within each story phase.
- Stop at each checkpoint and run the story's independent test before moving to the next priority.
- Do not implement cleanup, SOG compression, merge, NanoGS, LOD, PlayCanvas packaging, or mega-patching in this feature.
