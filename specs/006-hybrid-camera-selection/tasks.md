# Tasks: Hybrid Camera Selection

**Input**: Design documents from `specs/006-hybrid-camera-selection/`  
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Included. This feature replaces a sensitive algorithm and has measurable selector, diagnostics, and resume/reuse requirements.

**Organization**: Tasks are grouped by user story so each story can be implemented and validated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other tasks in the same phase because it touches different files or independent test fixtures
- **[Story]**: Maps to a user story from `spec.md`
- Every task includes an exact file path

## Phase 1: Setup

**Purpose**: Align the existing Feature 3 patching code and tests with the Feature 006 design before implementation starts.

- [ ] T001 Review the current selector entrypoints and call sites in `src/reefs/patches/selection.py`, `src/reefs/splat/pipeline.py`, and `src/reefs/diagnostics/patch_plots.py`
- [ ] T002 [P] Add compact selector fixture builders for synthetic sparse scenes, patch bounds, camera intrinsics, and image observations in `tests/fixtures/patch_selection.py`
- [ ] T003 [P] Add validation fixture paths and expected diagnostic filenames for the existing test dataset in `tests/fixtures/patch_selection_paths.py`

---

## Phase 2: Foundational

**Purpose**: Shared data structures and helpers that block all user stories.

**Critical**: No user story implementation should begin until this phase is complete.

- [ ] T004 Add camera intrinsics parsing and projection primitives for COLMAP text sparse models in `src/reefs/patches/visibility.py`
- [ ] T005 Add patch target sample generation, body/boundary labelling, and local cell indexing in `src/reefs/patches/visibility.py`
- [ ] T006 Add density weighting helpers for sparse target points in `src/reefs/patches/visibility.py`
- [ ] T007 Extend selector diagnostic data classes and serialisation fields in `src/reefs/patches/selection.py`
- [ ] T008 Add selector signature construction for selector-affecting settings and source sparse fingerprints in `src/reefs/patches/selection.py`
- [ ] T009 Update patch metadata validation to require `selector.name`, `selector.version`, `selector.signature`, and selector coverage summaries in `src/reefs/patches/validation.py`
- [ ] T010 [P] Add unit tests for camera intrinsics parsing and point projection in `tests/unit/test_patch_visibility.py`
- [ ] T011 [P] Add unit tests for target sample body/boundary labelling and density weights in `tests/unit/test_patch_visibility.py`
- [ ] T012 [P] Add unit tests for selector metadata validation and signature changes in `tests/unit/test_patch_selection_reuse.py`

**Checkpoint**: Target-region, projection, density, metadata, and selector-signature foundations are ready.

---

## Phase 3: User Story 1 - Select Robust Patch Cameras (Priority: P1)

**Goal**: Generate selected patch image sets that cover patch bodies, support boundaries, avoid irrelevant halo-heavy cameras where possible, and respect `patching.max_cameras`.

**Independent Test**: Run the selector on synthetic sparse-hole, local-camera-points-away, and dense-cluster fixtures without running LFS training; selected cameras stay within the cap and improve target coverage over the old ranking behaviour.

### Tests for User Story 1

- [ ] T013 [P] [US1] Add failing unit tests for either-signal track/projection fusion in `tests/unit/test_patch_selection.py`
- [ ] T014 [P] [US1] Add failing unit tests for target-image-share spillover penalties in `tests/unit/test_patch_selection.py`
- [ ] T015 [P] [US1] Add failing unit tests for greedy marginal camera selection under `patching.max_cameras` in `tests/unit/test_patch_selection.py`
- [ ] T016 [P] [US1] Add failing synthetic tests for sparse-hole, local-camera-points-away, and dense-cluster cases in `tests/unit/test_patch_selection.py`

### Implementation for User Story 1

- [ ] T017 [US1] Implement candidate discovery from local cameras, one-ring support cameras, target track observers, and target projection observers in `src/reefs/patches/selection.py`
- [ ] T018 [US1] Implement track evidence scoring with body/boundary separation and density weighting in `src/reefs/patches/selection.py`
- [ ] T019 [US1] Implement geometric projection evidence scoring with body/boundary sample visibility in `src/reefs/patches/selection.py`
- [ ] T020 [US1] Implement target-image-share and spillover penalty calculation in `src/reefs/patches/selection.py`
- [ ] T021 [US1] Implement either-signal target evidence fusion in `src/reefs/patches/selection.py`
- [ ] T022 [US1] Implement greedy marginal selection and replace the old boundary-first balanced selection call in `src/reefs/patches/selection.py`
- [ ] T023 [US1] Update patch sparse export inputs to consume the Target-Aware Spatial Greedy selected image set without changing source SfM outputs in `src/reefs/patches/export.py`

**Checkpoint**: User Story 1 works independently for synthetic and fixture patch scenes.

---

## Phase 4: User Story 2 - Protect Boundaries Without Hollowing Interiors (Priority: P2)

**Goal**: Preserve broad local acquisition coverage while retaining useful boundary and oblique support cameras.

**Independent Test**: Known problematic reef patches and Polish-town style fixtures show no hollow local acquisition strip while maintaining boundary coverage and useful support-view selection.

### Tests for User Story 2

- [ ] T024 [P] [US2] Add failing unit tests for local camera-position cell protection in `tests/unit/test_patch_selection.py`
- [ ] T025 [P] [US2] Add failing unit tests for view azimuth/elevation diversity bonuses in `tests/unit/test_patch_selection.py`
- [ ] T026 [P] [US2] Add failing tests that nonlocal support cameras can beat weak local cameras without a fixed support quota in `tests/unit/test_patch_selection.py`
- [ ] T027 [P] [US2] Add an integration test for known reef-style hollow-strip prevention in `tests/integration/test_splat_hybrid_camera_selection.py`

### Implementation for User Story 2

- [ ] T028 [US2] Add local camera-position cell coverage state and marginal gain to the greedy selector in `src/reefs/patches/selection.py`
- [ ] T029 [US2] Add azimuth/elevation view-bin diversity state and marginal gain to the greedy selector in `src/reefs/patches/selection.py`
- [ ] T030 [US2] Add soft nonlocal/support penalties that do not create a hard support quota in `src/reefs/patches/selection.py`
- [ ] T031 [US2] Add poor body, boundary, local-cell, and excessive-support warning generation in `src/reefs/patches/selection.py`
- [ ] T032 [US2] Define named default warning thresholds for meaningful target coverage, small target share, and excessive support use in `src/reefs/patches/selection.py`
- [ ] T033 [US2] Update patch metadata writing with selector coverage metrics, warning flags, and warning threshold values in `src/reefs/patches/export.py`

**Checkpoint**: User Story 2 works independently for reef and oblique-support fixture scenarios.

---

## Phase 5: User Story 3 - Audit Selection Decisions (Priority: P3)

**Goal**: Produce diagnostics that make selected/rejected local/support decisions, coverage, spillover risk, and warnings inspectable without terminal logs.

**Independent Test**: Every generated patch has metadata, `camera_coverage.csv`, `generation.log`, and plots that distinguish selected local, rejected local, selected support/nonlocal, and unused support/nonlocal cameras.

### Tests for User Story 3

- [ ] T034 [P] [US3] Add failing diagnostic CSV contract tests in `tests/unit/test_patch_selection_diagnostics.py`
- [ ] T035 [P] [US3] Add failing plot-generation tests for selected/rejected local/support groups in `tests/unit/test_patch_selection_diagnostics.py`
- [ ] T036 [P] [US3] Add failing integration test that plot export failure records a warning but leaves valid patch outputs usable in `tests/integration/test_splat_hybrid_camera_selection.py`

### Implementation for User Story 3

- [ ] T037 [US3] Write the Feature 006 `camera_coverage.csv` columns from selector diagnostics in `src/reefs/diagnostics/patch_plots.py`
- [ ] T038 [US3] Update per-patch `plot.png` and `plot.html` generation to distinguish selected local, rejected local, selected support/nonlocal, and unused support/nonlocal cameras in `src/reefs/diagnostics/patch_plots.py`
- [ ] T039 [US3] Add target/body, boundary, local-cell, target-share, view-bin, and warning-threshold summaries to `generation.log` in `src/reefs/diagnostics/patch_plots.py`
- [ ] T040 [US3] Ensure non-critical diagnostic failures are recorded as warnings while valid selected sparse outputs remain trainable in `src/reefs/splat/pipeline.py`

**Checkpoint**: User Story 3 diagnostics are independently inspectable for a generated patch.

---

## Phase 6: User Story 4 - Replace The Selector Without New User Complexity (Priority: P4)

**Goal**: Existing patching commands use the Target-Aware Spatial Greedy selector without adding user-facing selector modes, and incompatible existing outputs are handled up front.

**Independent Test**: `uv run main.py --config <config.yml> --steps splat.patch` uses the Target-Aware Spatial Greedy selector, public configs expose no selector-mode choice, and old selector outputs trigger an up-front reuse/overwrite decision.

### Tests for User Story 4

- [ ] T041 [P] [US4] Add failing config/schema tests proving no public selector-mode key is accepted in `tests/unit/test_splat_config.py`
- [ ] T042 [P] [US4] Add failing reuse tests for incompatible selector signatures in `tests/unit/test_patch_selection_reuse.py`
- [ ] T043 [P] [US4] Add failing integration test for up-front overwrite/reuse decisions before patch work starts in `tests/integration/test_splat_hybrid_camera_selection.py`
- [ ] T044 [P] [US4] Add failing integration test for missing source sparse outputs or malformed patch metadata blocking before training starts in `tests/integration/test_splat_hybrid_camera_selection.py`

### Implementation for User Story 4

- [ ] T045 [US4] Remove old selector-mode wording and ensure public configs do not expose a selector-mode setting in `configs/example.yml`
- [ ] T046 [US4] Integrate selector signature checks with existing patch reuse decisions in `src/reefs/splat/resume.py`
- [ ] T047 [US4] Update run status, manifest, timings, and warnings with selector provenance and reuse decisions in `src/reefs/splat/pipeline.py`
- [ ] T048 [US4] Update README patching guidance to describe the single Target-Aware Spatial Greedy selector and diagnostic inspection in `README.MD`
- [ ] T049 [US4] Record the selector replacement decision and rationale in `docs/decisions.md`

**Checkpoint**: User Story 4 preserves the current user workflow while replacing the selector.

---

## Phase 7: Polish & Cross-Cutting

**Purpose**: Validate the complete feature and align Spec Kit/source guidance.

- [ ] T050 [P] Update `specs/003-splat-patching-training/plan.md` to say Feature 006 supersedes the old boundary-first selector
- [ ] T051 [P] Update `specs/003-splat-patching-training/data-model.md` to reference the Target-Aware Spatial Greedy selector metadata and warning semantics
- [ ] T052 [P] Update `specs/003-splat-patching-training/contracts/patch-artifacts.md` to point to Feature 006 selector artefacts
- [ ] T053 [P] Update `scratch/setup/old_pipeline_notes_updated_for_speckit.MD` so rebuilding from scratch would use the Target-Aware Spatial Greedy selector rather than the old track-balanced selector
- [ ] T054 Run the full automated suite with `uv run pytest -q`
- [ ] T055 Run the quickstart patch-only smoke check on the test dataset and inspect `splat/patches/p000/patch_diagnostics/`
- [ ] T056 Run patch-only diagnostics for Dataset 1 known problematic patches and record findings in `docs/troubleshooting.md` only if issues arise
- [ ] T057 Compare generated validation diagnostics against the scratch baseline metrics and write a concise validation summary in `scratch/camera_selection_experiments/feature006_validation_summary.md`
- [ ] T058 Run the Polish-town style oblique patch validation and add the outcome to `scratch/camera_selection_experiments/feature006_validation_summary.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup and blocks all user stories.
- **US1 (Phase 3)**: Depends on Foundational.
- **US2 (Phase 4)**: Depends on US1 scoring and selected-set state.
- **US3 (Phase 5)**: Can begin after US1 diagnostic records exist; final plot/log content depends on US2 warnings.
- **US4 (Phase 6)**: Depends on selector signature and metadata from US1/US2.
- **Polish (Phase 7)**: Depends on selected user stories being implemented.

### User Story Dependencies

- **US1**: MVP; required before any other story is useful.
- **US2**: Builds on US1 to solve the hollow-patch and oblique-support balance.
- **US3**: Audits US1/US2 decisions; partly parallel after diagnostic data classes exist.
- **US4**: Integrates the selector replacement into user workflow and reuse safety.

### Parallel Opportunities

- T002 and T003 can run in parallel.
- T010, T011, and T012 can run in parallel after T004-T009 interfaces are agreed.
- Tests inside each user-story phase marked `[P]` can be written in parallel.
- Documentation tasks T050-T053 can run in parallel after the implementation approach is stable.

---

## Parallel Example: User Story 1

```text
Task: "Add failing unit tests for either-signal track/projection fusion in tests/unit/test_patch_selection.py"
Task: "Add failing unit tests for target-image-share spillover penalties in tests/unit/test_patch_selection.py"
Task: "Add failing unit tests for greedy marginal camera selection under patching.max_cameras in tests/unit/test_patch_selection.py"
Task: "Add failing synthetic tests for sparse-hole, local-camera-points-away, and dense-cluster cases in tests/unit/test_patch_selection.py"
```

---

## Implementation Strategy

### MVP First

1. Complete Setup and Foundational phases.
2. Implement US1 and run only selector unit tests plus synthetic fixtures.
3. Stop and inspect selected camera sets before changing diagnostics or reuse behaviour.

### Incremental Delivery

1. US1: robust selected sets under the camera cap.
2. US2: body/boundary/local acquisition protection and warnings.
3. US3: diagnostics and warning visibility.
4. US4: user workflow, reuse/overwrite, and documentation.

### Validation Before Expensive Training

1. Run `uv run pytest -q`.
2. Run `splat.patch` only on the test dataset.
3. Run `splat.patch` only on known problematic Dataset 1/2 patches or full patch sets.
4. Compare outputs against scratch baseline metrics and run the Polish-town style validation.
5. Inspect diagnostics before launching any LFS training.
