# Tasks: Splat Cleanup And SOG Compression

**Input**: Design documents from `specs/005-splat-post-processing/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Included because the plan requires focused automated tests for source selection, cleanup, merge, SOG, validation, and resume behaviour.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested independently. Safety-critical resume/overwrite checks are foundational because they must run during preflight before any post-processing work starts.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and has no dependency on incomplete tasks.
- **[Story]**: Maps to user stories in [spec.md](spec.md).
- Every task includes an exact file path.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the post-processing module and test skeletons without changing runtime behaviour.

- [ ] T001 Create `src/reefs/postprocess/__init__.py` with package exports placeholder.
- [ ] T002 Create empty implementation modules `src/reefs/postprocess/artifacts.py`, `src/reefs/postprocess/cleanup.py`, `src/reefs/postprocess/merge.py`, `src/reefs/postprocess/pipeline.py`, `src/reefs/postprocess/resume.py`, and `src/reefs/postprocess/sog.py`.
- [ ] T003 [P] Create unit test skeleton files `tests/unit/test_postprocess_artifacts.py`, `tests/unit/test_postprocess_cleanup.py`, `tests/unit/test_postprocess_merge.py`, `tests/unit/test_postprocess_sog.py`, and `tests/unit/test_postprocess_validation.py`.
- [ ] T004 [P] Create integration test skeleton files `tests/integration/test_postprocess_mocked_success.py` and `tests/integration/test_postprocess_resume_overwrite.py`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared config, tool validation, existing-output detection, resume/overwrite decisions, records, and route plumbing that every post-processing story depends on.

**CRITICAL**: No user story work can begin until this phase is complete. All possible checks and resume/overwrite decisions must happen in preflight before any cleanup, merge, or SOG command can run.

- [ ] T005 Add cleanup, merge, and SOG config models to `src/reefs/config/models.py` matching `specs/005-splat-post-processing/contracts/config-schema.yml`.
- [ ] T006 [P] Add config loading tests for default cleanup, merge, and SOG settings in `tests/unit/test_splat_config.py`.
- [ ] T007 Resolve the cleanup backend implementation path and record the decision in `docs/decisions.md`.
- [ ] T008 Add post-processing tool validation helpers for cleanup backend availability and `splat-transform` merge/SOG capability checks in `src/reefs/preflight/tools.py`.
- [ ] T009 [P] Add tool validation tests for cleanup backend missing/available and `splat-transform` merge/SOG version/capability outcomes in `tests/unit/test_postprocess_validation.py`.
- [ ] T010 Add post-processing step names `splat.cleanup`, `splat.merge`, `splat.sog`, and `splat.postprocess` to CLI step routing in `src/reefs/cli.py`.
- [ ] T011 Add CLI step routing tests for `splat.cleanup`, `splat.merge`, `splat.sog`, and `splat.postprocess` in `tests/unit/test_cli_overrides.py`.
- [ ] T012 Add manifest path helpers for `splat/postprocess/postprocess_manifest.json`, `splat/merged/merged_splat.ply`, and `splat/sog/merged_splat.sog` in `src/reefs/io/paths.py`.
- [ ] T013 Add stage constants and run-record helpers for `splat.cleanup`, `splat.cleanup.<patch_id>`, `splat.merge`, `splat.sog`, and `splat.postprocess` in `src/reefs/runs/status.py` and `src/reefs/runs/recorder.py`.
- [ ] T014 Implement filesystem and manifest-based post-processing output detection in `src/reefs/postprocess/resume.py`.
- [ ] T015 Implement post-processing reuse/overwrite/fail decision planning before work starts in `src/reefs/postprocess/resume.py`.
- [ ] T016 Implement config-diff warning extraction for cleanup, merge, SOG, and source-selection settings in `src/reefs/postprocess/resume.py`.
- [ ] T017 Ensure overwrite removes only generated cleaned, merged, SOG, and post-processing manifest outputs in `src/reefs/postprocess/resume.py`.
- [ ] T018 Add existing-output detection tests for cleaned patch outputs, merged PLY, final SOG, and previous post-processing manifest in `tests/unit/test_postprocess_validation.py`.
- [ ] T019 Add resume decision tests for reuse, overwrite, fail, non-interactive missing decision, and config-diff warning cases in `tests/unit/test_resume_decisions.py`.
- [ ] T020 Add post-processing preflight checks to `src/reefs/preflight/splat.py` for Feature 3 training outputs, requested steps, required tools, existing outputs, and up-front decision requirements.
- [ ] T021 [P] Add foundational preflight and run-record tests for requested post-processing steps in `tests/integration/test_postprocess_mocked_success.py`.

**Checkpoint**: Foundation ready - post-processing steps can be routed, configured, validated, checked for existing outputs, and given resume/overwrite decisions before story logic runs.

---

## Phase 3: User Story 1 - Clean Trained Patch Splats (Priority: P1) MVP

**Goal**: Select trained patch splat sources, classify completion severity, run cleanup, and record per-patch cleanup status.

**Independent Test**: Run `--steps splat.cleanup` against mocked Feature 3 patch outputs and confirm every eligible patch is complete, warning, severe warning, failed, skipped, or reused with concise records.

### Tests for User Story 1

- [ ] T022 [P] [US1] Add source-selection unit tests for `splat_finished.ply`, highest-iteration fallback, no usable PLY, and 80 percent severity thresholds in `tests/unit/test_postprocess_artifacts.py`.
- [ ] T023 [P] [US1] Add PLY vertex-count unit tests for ASCII/binary header counts and missing-count failures in `tests/unit/test_postprocess_artifacts.py`.
- [ ] T024 [P] [US1] Add cleanup adapter unit tests for successful cleanup, backend unavailable, cleanup no-output, and scene-relative setting propagation in `tests/unit/test_postprocess_cleanup.py`.
- [ ] T025 [P] [US1] Add cleanup-only integration test with mocked cleanup backend and mixed complete/incomplete patch sources in `tests/integration/test_postprocess_mocked_success.py`.

### Implementation for User Story 1

- [ ] T026 [US1] Implement patch training source discovery, source selection, severity classification, and deterministic cleaned-output naming in `src/reefs/postprocess/artifacts.py`.
- [ ] T027 [US1] Implement lightweight PLY vertex-count parsing for before/after splat counts in `src/reefs/postprocess/artifacts.py`.
- [ ] T028 [US1] Implement cleanup backend adapter using evidenced coral cleanup settings in `src/reefs/postprocess/cleanup.py`.
- [ ] T029 [US1] Implement cleanup manifest updates and per-patch cleanup status records in `src/reefs/postprocess/pipeline.py`.
- [ ] T030 [US1] Integrate `splat.cleanup` CLI execution path in `src/reefs/cli.py`.
- [ ] T031 [US1] Update run status and timings after every cleaned patch in `src/reefs/runs/recorder.py`.
- [ ] T032 [US1] Update warning text so cleanup settings are described as scene-relative values in `src/reefs/postprocess/cleanup.py`.

**Checkpoint**: User Story 1 should be fully functional and testable independently with `--steps splat.cleanup`.

---

## Phase 4: User Story 2 - Merge Cleaned Patches Into One Site Splat (Priority: P1)

**Goal**: Merge available cleaned patch PLYs into one primary cleaned site-level PLY while recording every included/excluded patch.

**Independent Test**: Run `--steps splat.merge` after mocked cleaned outputs exist and confirm exactly one merged PLY is produced and all patches are listed as included or excluded.

### Tests for User Story 2

- [ ] T033 [P] [US2] Add merge input selection unit tests for all-cleaned, missing-cleaned, failed-cleanup, and incomplete-source warning cases in `tests/unit/test_postprocess_merge.py`.
- [ ] T034 [P] [US2] Add `splat-transform` merge command construction tests for cleaned PLY inputs, output path, overwrite flag, and relative command summary in `tests/unit/test_postprocess_merge.py`.
- [ ] T035 [P] [US2] Add merge integration test with mocked `splat-transform` and missing cleaned patches continuing by default in `tests/integration/test_postprocess_mocked_success.py`.

### Implementation for User Story 2

- [ ] T036 [US2] Implement cleaned patch input inventory and included/excluded merge records in `src/reefs/postprocess/merge.py`.
- [ ] T037 [US2] Implement `splat-transform` cleaned PLY merge command construction and streaming command logging in `src/reefs/postprocess/merge.py`.
- [ ] T038 [US2] Implement merge manifest updates, severe-warning summary, and valid merged PLY status in `src/reefs/postprocess/pipeline.py`.
- [ ] T039 [US2] Integrate `splat.merge` CLI execution path in `src/reefs/cli.py`.
- [ ] T040 [US2] Update run manifest and timings for `splat.merge` in `src/reefs/runs/recorder.py`.

**Checkpoint**: User Story 2 should produce one merged cleaned site-level PLY and remain testable independently after cleanup.

---

## Phase 5: User Story 3 - Export Final Site SOG (Priority: P2)

**Goal**: Convert the merged cleaned site-level PLY into one final SOG output by default.

**Independent Test**: Run `--steps splat.sog` from an existing merged cleaned PLY and confirm one SOG output, source reference, timing, warning summary, and failure status behaviour.

### Tests for User Story 3

- [ ] T041 [P] [US3] Add SOG command construction tests for merged source, final output, nan filtering, harmonics filtering, and optional iterations in `tests/unit/test_postprocess_sog.py`.
- [ ] T042 [P] [US3] Add SOG preflight tests for missing merged PLY, missing `splat-transform`, unsupported `splat-transform`, and SOG disabled cases in `tests/unit/test_postprocess_validation.py`.
- [ ] T043 [P] [US3] Add SOG integration tests for successful export and SOG failure after valid merge preserving merged PLY with partial status in `tests/integration/test_postprocess_mocked_success.py`.

### Implementation for User Story 3

- [ ] T044 [US3] Implement final SOG source resolution and output path handling in `src/reefs/postprocess/sog.py`.
- [ ] T045 [US3] Implement `splat-transform` SOG command construction and streaming command logging in `src/reefs/postprocess/sog.py`.
- [ ] T046 [US3] Implement SOG manifest updates, failure reason capture, and partial post-processing status in `src/reefs/postprocess/pipeline.py`.
- [ ] T047 [US3] Integrate `splat.sog` and full `splat.postprocess` CLI execution paths in `src/reefs/cli.py`.
- [ ] T048 [US3] Update run manifest and timings for `splat.sog` and `splat.postprocess` in `src/reefs/runs/recorder.py`.

**Checkpoint**: User Story 3 should create one final SOG from an existing or newly merged cleaned site PLY.

---

## Phase 6: User Story 4 - Resume Or Overwrite Post-Processing Safely (Priority: P2)

**Goal**: Prove reuse, overwrite, fail, and config-change decisions are gathered up front for cleanup, merge, and SOG.

**Independent Test**: Create existing cleaned, merged, and SOG outputs, then run requested stages with resume, overwrite, and fail policies and confirm all decisions are recorded before any work begins.

### Tests for User Story 4

- [ ] T049 [P] [US4] Add integration tests proving cleanup, merge, and SOG prompts/decisions are completed before any post-processing command runs in `tests/integration/test_postprocess_resume_overwrite.py`.
- [ ] T050 [P] [US4] Add integration test proving overwrite deletes or replaces generated post-processing outputs without modifying Feature 3 training outputs in `tests/integration/test_postprocess_resume_overwrite.py`.

### Implementation for User Story 4

- [ ] T051 [US4] Update run status so completed post-processing is not reported until all requested cleanup, merge, and SOG stages complete or are reused in `src/reefs/runs/status.py`.
- [ ] T052 [US4] Ensure terminal summary, warnings log, and top-level post-processing manifest warnings prominently list excluded patches and severe incomplete sources in `src/reefs/postprocess/pipeline.py`.

**Checkpoint**: User Story 4 should make reruns safe and should never prompt mid-run for known post-processing conflicts.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, config examples, workflow validation, and final quality checks.

- [ ] T053 [P] Update `configs/example.yml` with cleanup, merge, and SOG advanced settings using placeholder-safe comments.
- [ ] T054 [P] Update dataset config templates in `configs/datasets/` with cleanup, merge, and SOG settings consistent with `configs/example.yml`.
- [ ] T055 [P] Update `README.MD` with post-processing step commands, final artefact locations, and `splat-transform`/cleanup backend requirements.
- [ ] T056 [P] Update `docs/decisions.md` with the cleanup backend adapter decision and `splat-transform` merge/SOG decision.
- [ ] T057 [P] Update `docs/troubleshooting.md` with likely cleanup backend, missing merged PLY, and SOG conversion failure guidance.
- [ ] T058 Run `uv run pytest tests/unit/test_postprocess_artifacts.py tests/unit/test_postprocess_cleanup.py tests/unit/test_postprocess_merge.py tests/unit/test_postprocess_sog.py tests/unit/test_postprocess_validation.py`.
- [ ] T059 Run `uv run pytest tests/integration/test_postprocess_mocked_success.py tests/integration/test_postprocess_resume_overwrite.py`.
- [ ] T060 Run focused regression tests `uv run pytest tests/unit/test_splat_config.py tests/unit/test_cli_overrides.py tests/unit/test_resume_decisions.py tests/integration/test_splat_mocked_success.py`.
- [ ] T061 Run the quickstart smoke command on the local test dataset with `uv run main.py --config configs/test.yml --run-id <RUN_ID> --steps splat.postprocess --resume-policy overwrite`.
- [ ] T062 Record any non-obvious implementation issue and fix in `docs/troubleshooting.md`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup and blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational.
- **User Story 2 (Phase 4)**: Depends on Foundational and is most useful after US1 cleanup outputs exist.
- **User Story 3 (Phase 5)**: Depends on Foundational and requires a valid merged PLY from US2 or an existing selected merged PLY.
- **User Story 4 (Phase 6)**: Depends on the concrete cleanup, merge, and SOG outputs from US1-US3, with the core decision engine already present from Foundational.
- **Polish (Phase 7)**: Depends on desired user stories being complete.

### User Story Dependencies

- **US1 Clean Trained Patch Splats**: MVP. No dependency on other user stories after Foundational.
- **US2 Merge Cleaned Patches**: Depends on cleaned patch output contract from US1, but can be developed with fixtures.
- **US3 Export Final Site SOG**: Depends on merged PLY contract from US2, but can be developed with fixtures.
- **US4 Resume Or Overwrite Safely**: Cross-cuts US1-US3 and validates the foundational decision engine on concrete outputs.

### Parallel Opportunities

- T003 and T004 can run in parallel after T001-T002.
- T006, T009, T011, T018, T019, and T021 can run in parallel while foundational implementation tasks proceed.
- US1 tests T022-T025 can be written in parallel before US1 implementation.
- US2 tests T033-T035 can be written in parallel after merge contracts are understood.
- US3 tests T041-T043 can be written in parallel after SOG contracts are understood.
- US4 tests T049-T050 can be written in parallel once output paths are settled.
- Documentation/config polish tasks T053-T057 can run in parallel after behaviour is implemented.

---

## Parallel Example: User Story 1

```text
Task: "T022 [P] [US1] Add source-selection unit tests in tests/unit/test_postprocess_artifacts.py"
Task: "T024 [P] [US1] Add cleanup adapter unit tests in tests/unit/test_postprocess_cleanup.py"
Task: "T025 [P] [US1] Add cleanup-only integration test in tests/integration/test_postprocess_mocked_success.py"
```

## Parallel Example: User Story 2

```text
Task: "T033 [P] [US2] Add merge input selection unit tests in tests/unit/test_postprocess_merge.py"
Task: "T034 [P] [US2] Add splat-transform merge command construction tests in tests/unit/test_postprocess_merge.py"
Task: "T035 [P] [US2] Add merge integration test in tests/integration/test_postprocess_mocked_success.py"
```

## Parallel Example: User Story 3

```text
Task: "T041 [P] [US3] Add SOG command construction tests in tests/unit/test_postprocess_sog.py"
Task: "T042 [P] [US3] Add SOG preflight tests in tests/unit/test_postprocess_validation.py"
Task: "T043 [P] [US3] Add SOG integration tests in tests/integration/test_postprocess_mocked_success.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 setup.
2. Complete Phase 2 foundational routing/config/preflight/tool-validation/run-record/resume-decision tasks.
3. Complete Phase 3 cleanup-only tasks.
4. Stop and validate cleanup independently with `--steps splat.cleanup`.

### Incremental Delivery

1. Foundation: config, tool validation, existing-output detection, up-front decision planning, and route plumbing.
2. Cleanup MVP: source selection, cleanup adapter, per-patch status.
3. Merge: cleaned input inventory, `splat-transform` merge, merged PLY record.
4. SOG: final SOG export from merged PLY and partial status on SOG failure.
5. Resume/overwrite validation: prove no known conflict prompts mid-run.
6. Polish: configs, docs, quickstart smoke, and regression suite.

### Notes

- Do not implement COLMAP, patch generation, LFS training, PlayCanvas, NanoGS, or LOD tasks in this feature.
- Do not introduce private local paths into specs, configs, docs, or tests.
- If cleanup backend behaviour cannot be matched safely, stop and update `docs/troubleshooting.md` plus the relevant Spec Kit docs before continuing.
