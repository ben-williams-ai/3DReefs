# Tasks: COLMAP SfM Pipeline

**Input**: Design documents from `/specs/002-colmap-sfm-pipeline/`  
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`

**Tests**: Included because Feature 2 adds reusable orchestration, external-command mapping, preflight failure modes, and run-record behaviour.

**Organization**: Tasks are grouped by user story so the sparse SfM path can be delivered first, then validation/configuration/resume behaviour can be hardened incrementally.

## Phase 1: Setup

**Purpose**: Prepare shared package structure and local configuration placeholders.

- [x] T001 Add COLMAP, SfM, diagnostics, and preflight package files in `src/reefs/colmap/`, `src/reefs/sfm/`, `src/reefs/diagnostics/`, and `src/reefs/preflight/`
- [x] T002 Update public example config with placeholder `tools.vocab_tree_path` and `advanced.sfm` defaults in `configs/example.yml`
- [x] T003 Update ignored local test config with Feature 2 settings in `configs/test.yml`

---

## Phase 2: Foundational

**Purpose**: Implement shared configuration, command, logging, and run-record primitives that all SfM stories depend on.

- [x] T004 Extend typed config models for `tools.vocab_tree_path` and `advanced.sfm` in `src/reefs/config/models.py`
- [x] T005 [P] Add SfM config unit tests in `tests/unit/test_sfm_config.py`
- [x] T006 [P] Add COLMAP command builder tests in `tests/unit/test_colmap_commands.py`
- [x] T007 Implement COLMAP command builders and matching-mode expansion in `src/reefs/colmap/commands.py`
- [x] T008 Implement COLMAP subprocess logging and timing helper in `src/reefs/colmap/runner.py`
- [x] T009 Implement COLMAP sparse model inspection helpers in `src/reefs/colmap/outputs.py`
- [x] T010 Implement image-dimension and camera-source diagnostics in `src/reefs/diagnostics/images.py` and `src/reefs/diagnostics/cameras.py`
- [x] T011 Add shared SfM stage/status helpers in `src/reefs/sfm/validation.py` and `src/reefs/sfm/resume.py`

**Checkpoint**: Config parsing, command construction, and basic output inspection can be tested without running COLMAP.

---

## Phase 3: User Story 1 - Produce Sparse SfM Outputs Ready For Splatting (Priority: P1)

**Goal**: A researcher can run `--steps sfm` and produce sparse and undistorted SfM outputs without starting splatting work.

**Independent Test**: Run `uv run main.py --config configs/test.yml --steps sfm --resume-policy overwrite` on a valid local project and inspect run records plus `sfm/undistorted/`.

### Tests for User Story 1

- [x] T012 [P] [US1] Add mocked successful SfM integration test in `tests/integration/test_sfm_mocked_success.py`
- [x] T013 [P] [US1] Add sparse output selection unit tests in `tests/unit/test_colmap_outputs.py`

### Implementation for User Story 1

- [x] T014 [US1] Implement SfM pipeline orchestration through feature extraction, matching, reconstruction, model selection, and undistortion in `src/reefs/sfm/pipeline.py`
- [x] T015 [US1] Integrate `sfm` and `sfm.*` step dispatch into `src/reefs/cli.py`
- [x] T016 [US1] Write SfM output metadata into run manifest/status records from `src/reefs/sfm/pipeline.py`
- [x] T017 [US1] Ensure `logs/colmap.log` captures every COLMAP command, stdout/stderr, exit code, and elapsed time in `src/reefs/colmap/runner.py`

**Checkpoint**: User Story 1 should produce selected sparse and undistorted outputs using mocked COLMAP and be ready for local smoke testing.

---

## Phase 4: User Story 2 - Validate Reef Image Inputs Before Heavy SfM Work (Priority: P2)

**Goal**: Invalid image organisation, dimensions, camera-source warnings, and recoloured mirror problems fail or prompt before heavy work starts.

**Independent Test**: Use small fixtures with invalid layouts, mixed dimensions, mixed camera metadata, and recoloured mismatches.

### Tests for User Story 2

- [x] T018 [P] [US2] Add SfM preflight tests for image layout, dimensions, and recoloured mirror failures in `tests/unit/test_sfm_preflight.py`
- [x] T019 [P] [US2] Add integration test for non-interactive mixed-camera-source failure in `tests/integration/test_sfm_mocked_failures.py`

### Implementation for User Story 2

- [x] T020 [US2] Implement SfM preflight validation in `src/reefs/preflight/sfm.py`
- [x] T021 [US2] Implement beginner-friendly mixed camera-source prompt/fail handling in `src/reefs/preflight/sfm.py`
- [x] T022 [US2] Write full image diagnostics reports for invalid dimensions and recoloured mismatches from `src/reefs/preflight/sfm.py`

**Checkpoint**: Bad image inputs are rejected before COLMAP feature extraction starts.

---

## Phase 5: User Story 3 - Control Intrinsics And Reconstruction Strategy (Priority: P3)

**Goal**: Safe defaults and explicit choices exist for intrinsics, matching, and reconstruction backend.

**Independent Test**: Run configs covering default intrinsics selection, user `cameras.txt`, supported matching modes, global reconstruction, and incremental reconstruction with mocked COLMAP.

### Tests for User Story 3

- [x] T023 [P] [US3] Add intrinsics selection and `cameras.txt` validation tests in `tests/unit/test_sfm_intrinsics.py`
- [x] T024 [P] [US3] Add mocked backend and matching validation failure tests in `tests/integration/test_sfm_mocked_failures.py`

### Implementation for User Story 3

- [x] T025 [US3] Implement intrinsics selection, calibration-image recording, and `cameras.txt` validation in `src/reefs/sfm/intrinsics.py`
- [x] T026 [US3] Enforce vocabulary-tree and spatial matching prerequisites in `src/reefs/preflight/sfm.py`
- [x] T027 [US3] Validate selected COLMAP reconstruction backend availability before reconstruction in `src/reefs/preflight/sfm.py`
- [x] T028 [US3] Apply configured matching and reconstruction options in `src/reefs/colmap/commands.py`

**Checkpoint**: Intrinsics, matching, and reconstruction choices are auditable and fail early when required resources are missing.

---

## Phase 6: User Story 4 - Use Recoloured Images Only For Undistorted Splatting Inputs (Priority: P4)

**Goal**: Raw images are always used for SfM, while valid recoloured images can be used for undistortion.

**Independent Test**: Use a mirrored recoloured fixture and confirm feature extraction uses raw images while undistortion uses recoloured images.

### Tests for User Story 4

- [x] T029 [P] [US4] Add recoloured undistortion integration test in `tests/integration/test_sfm_recoloured_undistortion.py`

### Implementation for User Story 4

- [x] T030 [US4] Select raw or recoloured undistortion image root according to effective config in `src/reefs/sfm/pipeline.py`
- [x] T031 [US4] Record sparse image source and undistortion image source in manifest/status output in `src/reefs/sfm/pipeline.py`

**Checkpoint**: Recoloured images never enter feature extraction, matching, or sparse reconstruction.

---

## Phase 7: User Story 5 - Optionally Produce Dense And Mesh Outputs (Priority: P5)

**Goal**: Dense and mesh outputs remain disabled by default and can be enabled explicitly for small comparison runs.

**Independent Test**: Confirm default SfM skips dense/mesh, then mocked enabled dense/mesh commands run and record outputs.

### Tests for User Story 5

- [x] T032 [P] [US5] Add dense/mesh config and prerequisite tests in `tests/unit/test_sfm_config.py`

### Implementation for User Story 5

- [x] T033 [US5] Add dense and mesh command builders in `src/reefs/colmap/commands.py`
- [x] T034 [US5] Add optional dense and mesh stage execution and output recording in `src/reefs/sfm/pipeline.py`

**Checkpoint**: Dense and mesh are opt-in and never run during default SfM.

---

## Phase 8: User Story 6 - Resume Or Restart SfM Stages Explicitly (Priority: P6)

**Goal**: Prior SfM outputs and setting changes are resolved before any requested SfM stage starts.

**Independent Test**: Simulate partial SfM outputs and confirm decisions are recorded before execution, with non-interactive failure when no policy is supplied.

### Tests for User Story 6

- [x] T035 [P] [US6] Add SfM partial-output resume tests in `tests/unit/test_sfm_resume.py`
- [x] T036 [P] [US6] Add integration test for SfM partial output decisions in `tests/integration/test_sfm_partial_outputs.py`

### Implementation for User Story 6

- [x] T037 [US6] Extend partial-run discovery and decision mapping for SfM stages in `src/reefs/sfm/resume.py` and `src/reefs/cli.py`
- [x] T038 [US6] Ensure all SfM prompts and decisions complete before creating or running COLMAP stages in `src/reefs/cli.py`

**Checkpoint**: No SfM prompt appears mid-run unless an unexpected fatal error has already stopped the run.

---

## Phase 9: Polish & Validation

**Purpose**: Documentation, local smoke testing, output inspection, and task closure.

- [x] T039 Update README SfM/vocabulary-tree guidance in `README.MD`
- [x] T040 Update `docs/decisions.md` with Feature 2 implementation decisions
- [x] T041 Update `docs/troubleshooting.md` with any Feature 2 gotchas encountered
- [x] T042 Run automated tests with `uv run pytest tests/unit tests/integration`
- [x] T043 Run local COLMAP smoke test with `uv run main.py --config configs/test.yml --steps sfm --resume-policy overwrite`
- [x] T044 Inspect local smoke-test SfM outputs for sensible database, sparse model, undistorted output, camera pose, point distribution, timings, and logs
- [x] T045 Mark completed Feature 2 tasks in `specs/002-colmap-sfm-pipeline/tasks.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on setup; blocks all user stories.
- **US1 (Phase 3)**: Depends on foundational tasks and is the MVP path.
- **US2-US6 (Phases 4-8)**: Depend on foundational tasks and integrate with US1 pipeline orchestration.
- **Polish (Phase 9)**: Depends on implemented user stories.

### User Story Dependencies

- **US1**: Required before local end-to-end smoke testing.
- **US2**: Can be implemented after foundational diagnostics, but should be complete before running large data.
- **US3**: Requires command builders and preflight.
- **US4**: Requires US1 undistortion stage and US2 recoloured mirror validation.
- **US5**: Requires US1 undistorted workspace.
- **US6**: Requires CLI integration and stage state naming from US1.

### Parallel Opportunities

- T005, T006, T010 can be worked in parallel after T004 is understood.
- T012 and T013 can be written in parallel.
- T018 and T019 can be written in parallel.
- T023 and T024 can be written in parallel.
- Documentation tasks T039-T041 can be updated after implementation details settle.

---

## Implementation Strategy

### MVP First

1. Complete setup and foundational command/config/output primitives.
2. Implement US1 with mocked tests.
3. Run a local `--steps sfm` smoke test.
4. Harden preflight, intrinsics, recoloured-image, dense/mesh, and resume behaviour.
5. Re-run automated tests and local smoke test after each material change.

### Notes

- Keep command construction separate from execution so COLMAP behaviour can be tested without running heavy work.
- Public specs, docs, and example configs must use placeholders rather than local private paths.
- The ignored local `configs/test.yml` may point at local tools, vocabulary tree resources, and test data.
