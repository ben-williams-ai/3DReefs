# Tasks: Camera Selection V2

**Input**: Design documents from `specs/006-hybrid-camera-selection/`  
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Included. This feature replaces a sensitive selector and has explicit diagnostic acceptance criteria.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup

**Purpose**: Remove stale selector assumptions before rebuilding the selector.

- [x] T001 Review and delete stale body/boundary or buffer-ranked selector paths from `src/reefs/patches/selection.py`
- [x] T002 Review and delete stale body/boundary target labelling from `src/reefs/patches/visibility.py`
- [x] T003 Review diagnostic column names and plan field renames in `src/reefs/diagnostics/patch_plots.py`
- [x] T004 [P] Review existing selector tests for stale boundary-first expectations in `tests/unit/test_patch_selection.py`
- [x] T005 [P] Review existing visibility tests for stale fixed-grid expectations in `tests/unit/test_patch_visibility.py`

---

## Phase 2: Foundational

**Purpose**: Shared selector data and metadata that block all user stories.

**Critical**: No user story work should begin until this phase is complete.

- [x] T006 Define selector name/version/signature constants for Camera Selection V2 in `src/reefs/patches/selection.py`
- [x] T007 Implement scene-scaled target-cell allocation from registered image count and patch area in `src/reefs/patches/visibility.py`
- [x] T008 Implement aspect-aware target grid dimensions in `src/reefs/patches/visibility.py`
- [x] T009 Implement adaptive per-cell height sampling with robust local, neighbouring, and patch-level fallback heights in `src/reefs/patches/visibility.py`
- [x] T010 Implement footprint target sample records without body/boundary roles in `src/reefs/patches/visibility.py`
- [x] T011 Update selector metadata fields for target cell count, grid dimensions, coverage, target image share, selector version, and warnings in `src/reefs/patches/selection.py`
- [x] T012 Update patch metadata validation for the new selector fields and incompatible selector signatures in `src/reefs/patches/validation.py`
- [x] T013 [P] Add unit tests for scene-scaled target-cell allocation in `tests/unit/test_patch_visibility.py`
- [x] T014 [P] Add unit tests for aspect-aware grid dimensions in `tests/unit/test_patch_visibility.py`
- [x] T015 [P] Add unit tests for adaptive height sampling on flat, vertical, empty-cell, and outlier-heavy fixtures in `tests/unit/test_patch_visibility.py`
- [x] T016 [P] Add unit tests proving target samples do not carry a privileged boundary/buffer role in `tests/unit/test_patch_visibility.py`

**Checkpoint**: Target representation and selector metadata are ready.

---

## Phase 3: User Story 1 - Cover The Full Patch Footprint (Priority: P1) 🎯 MVP

**Goal**: Select cameras using the full patch footprint, including low-texture areas.

**Independent Test**: Unit tests and patch diagnostics show known reef patches no longer lose obvious footprint strips before any LFS training.

### Tests for User Story 1

- [x] T017 [P] [US1] Add tests that low-texture footprint cells can be covered by geometric visibility without sparse tracks in `tests/unit/test_patch_selection.py`
- [x] T018 [P] [US1] Add tests that dense sparse-point clusters do not dominate full-footprint target coverage in `tests/unit/test_patch_selection.py`
- [x] T019 [P] [US1] Add tests for Dataset 1 patch800 `p002`-style sparse-corner behaviour in `tests/unit/test_patch_selection.py`

### Implementation for User Story 1

- [x] T020 [US1] Implement geometric projection evidence over the full footprint target in `src/reefs/patches/selection.py`
- [x] T021 [US1] Implement matched-track evidence over patch points with density weighting in `src/reefs/patches/selection.py`
- [x] T022 [US1] Implement either-signal usefulness fusion for matched tracks or geometric footprint visibility in `src/reefs/patches/selection.py`
- [x] T023 [US1] Implement target-image-share scoring from projected target samples in `src/reefs/patches/selection.py`
- [x] T024 [US1] Remove any separate buffer, edge, or boundary scoring from candidate usefulness and marginal gain in `src/reefs/patches/selection.py`

**Checkpoint**: User Story 1 works independently with diagnostics-only validation.

---

## Phase 4: User Story 2 - Choose Useful Internal And External Cameras (Priority: P2)

**Goal**: Select useful internal and external cameras without arbitrary location preference.

**Independent Test**: Diagnostics for reef and Polish-town style patches show useful internal cameras retained and useful external cameras included when justified.

### Tests for User Story 2

- [x] T025 [P] [US2] Add tests that useful internal cameras are not discarded while camera capacity remains in `tests/unit/test_patch_selection.py`
- [x] T026 [P] [US2] Add tests that internal cameras pointing outside the footprint can be rejected in `tests/unit/test_patch_selection.py`
- [x] T027 [P] [US2] Add tests that useful external cameras from one-ring neighbours can be selected in `tests/unit/test_patch_selection.py`
- [x] T028 [P] [US2] Add tests that non-neighbour external cameras require direct matched-track or geometric footprint evidence in `tests/unit/test_patch_selection.py`
- [x] T029 [P] [US2] Add tests that selection continues until camera cap or no useful candidates remain in `tests/unit/test_patch_selection.py`

### Implementation for User Story 2

- [x] T030 [US2] Implement candidate discovery for internal cameras, one-ring external cameras, matched-track cameras, and geometric-target cameras in `src/reefs/patches/selection.py`
- [x] T031 [US2] Implement internal/external candidate roles and candidate source labels in `src/reefs/patches/selection.py`
- [x] T032 [US2] Implement marginal selection over useful footprint coverage, track evidence, target image share, and small view-direction tie-breaks in `src/reefs/patches/selection.py`
- [x] T033 [US2] Implement rejection reasons for outside-looking cameras, tiny target sliver views, weaker useful candidates, and cap overflow in `src/reefs/patches/selection.py`
- [x] T034 [US2] Update selected image export inputs to consume the new selected camera set in `src/reefs/patches/export.py`

**Checkpoint**: User Story 2 works independently with internal/external diagnostics.

---

## Phase 5: User Story 3 - Preserve Useful Old Behaviour Without Extra Modes (Priority: P3)

**Goal**: Use one selector while preserving useful tracks, projected footprint evidence, view diversity, and reuse safety.

**Independent Test**: Existing patch commands use the V2 selector without public selector-mode config and incompatible outputs prompt before patching.

### Tests for User Story 3

- [x] T035 [P] [US3] Add config tests proving no selector-mode key is accepted in public splat config in `tests/unit/test_splat_config.py`
- [x] T036 [P] [US3] Add selector signature reuse tests for incompatible old patch outputs in `tests/unit/test_patch_reuse.py`
- [x] T037 [P] [US3] Add integration test for up-front overwrite/reuse decision before patch work starts in `tests/integration/test_splat_hybrid_camera_selection.py`

### Implementation for User Story 3

- [x] T038 [US3] Remove selector-mode handling and legacy selector branches from `src/reefs/splat/pipeline.py`
- [x] T039 [US3] Integrate selector signature checks with existing patch reuse decisions in `src/reefs/splat/resume.py`
- [x] T040 [US3] Update run records and warnings with selector provenance and reuse decisions in `src/reefs/splat/pipeline.py`
- [x] T041 [US3] Update public config comments to avoid selector-mode options in `configs/example.yml`

**Checkpoint**: User Story 3 preserves one-selector workflow.

---

## Phase 6: User Story 4 - Inspect Selection Decisions (Priority: P4)

**Goal**: Produce clear visual and tabular diagnostics for camera decisions.

**Independent Test**: Patch diagnostics expose selected/rejected internal and external cameras, footprint coverage, target image share, sparse-track evidence, and warnings.

### Tests for User Story 4

- [x] T042 [P] [US4] Add diagnostic CSV contract tests for Camera Selection V2 columns in `tests/unit/test_patch_selection_diagnostics.py`
- [x] T043 [P] [US4] Add diagnostic plot tests for selected internal, rejected internal, selected external, and unused external categories in `tests/unit/test_patch_selection_diagnostics.py`
- [x] T044 [P] [US4] Add warning-only diagnostic export failure test in `tests/integration/test_splat_hybrid_camera_selection.py`

### Implementation for User Story 4

- [x] T045 [US4] Update `camera_coverage.csv` writing with Camera Selection V2 columns in `src/reefs/diagnostics/patch_plots.py`
- [x] T046 [US4] Update `plot.png` and `plot.html` labels and colours for internal/external categories in `src/reefs/diagnostics/patch_plots.py`
- [x] T047 [US4] Update `generation.log` with footprint coverage, target image share, sparse-track evidence, selector version, and warnings in `src/reefs/diagnostics/patch_plots.py`
- [x] T048 [US4] Ensure diagnostic export failures remain warning-only when selected patch outputs are valid in `src/reefs/splat/pipeline.py`

**Checkpoint**: User Story 4 diagnostics are inspectable without terminal logs.

---

## Phase 7: Polish & Cross-Cutting

**Purpose**: Validate the feature and align documentation.

- [x] T049 [P] Update `README.MD` to describe the single Camera Selection V2 behaviour and diagnostics-only validation
- [x] T050 [P] Update `scratch/setup/old_pipeline_notes_updated_for_speckit.MD` so future rebuilds use Camera Selection V2 with scene-scaled footprint targets
- [x] T051 [P] Add a concise decision note for Camera Selection V2 in `docs/decisions.md`
- [x] T052 Run `uv run pytest -q tests/unit/test_patch_visibility.py tests/unit/test_patch_selection.py tests/unit/test_patch_selection_diagnostics.py tests/unit/test_patch_validation.py tests/unit/test_patch_reuse.py tests/unit/test_splat_config.py tests/integration/test_splat_hybrid_camera_selection.py`
- [x] T053 Generate diagnostics-only comparison for Dataset 1 patch800 `p002` and summarise it in `scratch/camera_selection_v2_comparison/dataset1_patch800_p002/summary.md`
- [x] T054 Generate diagnostics-only comparison for Dataset 1 patch400 `p007` and summarise it in `scratch/camera_selection_v2_comparison/dataset1_patch400_p007/summary.md`
- [x] T055 Generate Polish-town style diagnostic comparison and summarise it in `scratch/camera_selection_v2_comparison/polish_town/summary.md`
- [x] T056 Write validation findings, selector runtime, selected/rejected internal and external counts, footprint coverage, target-image-share summaries, and visual gap notes in `scratch/camera_selection_experiments/feature006_validation_summary.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup and blocks all user stories.
- **US1 (Phase 3)**: Depends on Foundational.
- **US2 (Phase 4)**: Depends on US1.
- **US3 (Phase 5)**: Depends on selector metadata from Foundational and can run after US1.
- **US4 (Phase 6)**: Depends on selector diagnostics from US1/US2.
- **Polish (Phase 7)**: Depends on all required user stories.

### User Story Dependencies

- **US1 (P1)**: MVP; required before useful diagnostics.
- **US2 (P2)**: Builds on US1 candidate scoring.
- **US3 (P3)**: Integrates selector provenance and reuse safety.
- **US4 (P4)**: Makes decisions inspectable.

### Parallel Opportunities

- T004 and T005 can run in parallel.
- T013 through T016 can run in parallel after T007-T010 interfaces are clear.
- Tests marked `[P]` inside each user story can be written in parallel.
- Documentation tasks T049-T051 can run in parallel after implementation stabilises.

---

## Parallel Example: User Story 1

```text
Task: "Add tests that low-texture footprint cells can be covered by geometric visibility without sparse tracks in tests/unit/test_patch_selection.py"
Task: "Add tests that dense sparse-point clusters do not dominate full-footprint target coverage in tests/unit/test_patch_selection.py"
Task: "Add tests for Dataset 1 patch800 p002-style sparse-corner behaviour in tests/unit/test_patch_selection.py"
```

---

## Implementation Strategy

### MVP First

1. Complete Setup and Foundational phases.
2. Complete US1 only.
3. Run selector unit tests and generate diagnostics for known reef patches.
4. Stop and inspect diagnostics before touching training.

### Incremental Delivery

1. US1: full-footprint camera usefulness.
2. US2: internal/external candidate balance.
3. US3: one-selector workflow and reuse safety.
4. US4: diagnostics.
5. Polish: docs and diagnostics-only validation.

### Validation Boundary

Feature 006 is complete when patch diagnostics satisfy the success criteria.
Do not require splat training, cleanup, merge, or SOG to accept this feature.
