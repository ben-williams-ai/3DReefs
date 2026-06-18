# Tasks: Camera Selection V3

**Input**: Design documents from `specs/009-camera-selection-v3/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/
**Tests**: Included because the feature requires selector, config, bounds, diagnostics, and validation checks.
**Organization**: Tasks are grouped by user story so each story can be implemented and tested independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other tasks in the same phase when file paths do not overlap
- **[Story]**: Which user story this task belongs to
- Every task includes an exact file path

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add shared config and selector identity before story work.

- [X] T001 Add `external_support_fraction` default and validation to `src/reefs/config/models.py`
- [X] T002 [P] Document `advanced.splat.patching.external_support_fraction` in `configs/example.yml`
- [X] T003 [P] Add dataset config comments for `external_support_fraction` in `configs/datasets/dataset_01.yml`
- [X] T004 [P] Add dataset config comments for `external_support_fraction` in `configs/datasets/dataset_02.yml`
- [X] T005 Update selector name/version/signature constants for V3 in `src/reefs/patches/selection.py`
- [X] T006 Add config default and validation coverage for `external_support_fraction` in `tests/unit/test_splat_config.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish V3 data structures, geometry helpers, and pipeline wiring used by all stories.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T007 Define V3 camera evidence and selection dataclasses in `src/reefs/patches/selection.py`
- [X] T008 Implement patch target derivation helper for external allowance and internal target in `src/reefs/patches/selection.py`
- [X] T009 Add unit tests for external allowance and internal target derivation in `tests/unit/test_patch_selection.py`
- [X] T010 Update patch-affecting config persistence to include selector signature and `external_support_fraction` in `src/reefs/splat/resume.py`
- [X] T011 Update patch metadata export fields for V3 counts, settings, and selector coverage in `src/reefs/patches/export.py`
- [X] T012 Update patch metadata validation for V3 selector name, coverage keys, and cap invariants in `src/reefs/patches/validation.py`
- [X] T013 Add validation tests for V3 selector metadata and cap invariants in `tests/unit/test_patch_validation.py`

**Checkpoint**: V3 config, data structures, metadata, and validation contracts are ready.

---

## Phase 3: User Story 1 - Preserve Useful Internal Patch Cameras (Priority: P1) 🎯 MVP

**Goal**: Keep useful internal patch cameras first and reject only unuseful internal cameras.

**Independent Test**: Run selector unit tests that build synthetic internal strip and bend cases and verify useful internal cameras are kept before any external support is selected.

### Tests for User Story 1

- [X] T014 [US1] Add synthetic test for useful internal cameras never being replaced by support cameras in `tests/unit/test_patch_selection.py`
- [X] T015 [US1] Add synthetic test for unuseful internal cameras being rejected by target image share and evidence rules in `tests/unit/test_patch_selection.py`
- [X] T016 [US1] Add synthetic Dataset-1-p002-style internal strip retention test in `tests/unit/test_patch_selection.py`
- [X] T017 [US1] Add synthetic Dataset-1-p007-style bend camera retention test in `tests/unit/test_patch_selection.py`

### Implementation for User Story 1

- [X] T018 [US1] Implement patch point track counting per candidate camera in `src/reefs/patches/selection.py`
- [X] T019 [US1] Implement patch rectangle and camera XY frustum footprint overlap scoring in `src/reefs/patches/selection.py`
- [X] T020 [US1] Implement target image share scoring from projected patch/frustum intersection in `src/reefs/patches/selection.py`
- [X] T021 [US1] Implement useful internal camera classification using target image share plus track or footprint evidence in `src/reefs/patches/selection.py`
- [X] T022 [US1] Implement final selection step that keeps all useful internal cameras before external support in `src/reefs/patches/selection.py`
- [X] T023 [US1] Remove old boundary-first ranking and balanced-sector internal thinning from `src/reefs/patches/selection.py`

**Checkpoint**: User Story 1 is independently functional and testable with internal-only selector behaviour.

---

## Phase 4: User Story 2 - Add Only Capped Neighbouring External Support (Priority: P1)

**Goal**: Add optional one-ring external support without exceeding support allowance, final cap, or neighbour constraints.

**Independent Test**: Run selector tests that verify internal-only mode, neighbour-only external eligibility, non-neighbour exclusion, support capping, and evidence-plus-azimuth ranking.

### Tests for User Story 2

- [X] T024 [US2] Add test that `external_support_fraction = 0` selects only useful internal cameras in `tests/unit/test_patch_selection.py`
- [X] T025 [US2] Add test that external candidates come only from one-ring neighbouring patches in `tests/unit/test_patch_selection.py`
- [X] T026 [US2] Add test that non-neighbour external cameras are excluded despite good evidence in `tests/unit/test_patch_selection.py`
- [X] T027 [US2] Add test that selected external support is capped by external allowance and remaining capacity in `tests/unit/test_patch_selection.py`
- [X] T028 [US2] Add test that external ranking balances evidence and azimuth spread in `tests/unit/test_patch_selection.py`

### Implementation for User Story 2

- [X] T029 [US2] Update `select_patch_views` signature to accept `external_support_fraction` and fixed V3 thresholds in `src/reefs/patches/selection.py`
- [X] T030 [US2] Implement neighbouring external candidate collection with source patch tracking in `src/reefs/patches/selection.py`
- [X] T031 [US2] Implement useful external classification using the same three evidence signals in `src/reefs/patches/selection.py`
- [X] T032 [US2] Implement greedy external support ranking with evidence score and azimuth spread in `src/reefs/patches/selection.py`
- [X] T033 [US2] Implement support allowance and final cap enforcement for selected external cameras in `src/reefs/patches/selection.py`
- [X] T034 [US2] Update splat patch generation to pass `external_support_fraction` into selection in `src/reefs/splat/pipeline.py`

**Checkpoint**: User Stories 1 and 2 both work independently with V3 support selection.

---

## Phase 5: User Story 3 - Size Patch Bounds For Internal Cameras (Priority: P2)

**Goal**: Create patch bounds using the internal camera target while preserving the final camera cap for selected cameras.

**Independent Test**: Generate bounds with `max_cameras: 400` and `external_support_fraction: 0.10` and verify wildflow receives `max_cameras=360` while validation still enforces the final cap of 400.

### Tests for User Story 3

- [X] T035 [P] [US3] Add bounds test that wildflow receives `internal_patch_target` instead of final cap in `tests/unit/test_patch_bounds.py`
- [X] T036 [P] [US3] Add pipeline patch generation test for deriving target 360 from cap 400 and support 0.10 in `tests/unit/test_splat_pipeline.py`
- [X] T037 [US3] Add test that useful internal count exceeding final cap is treated as a defect in `tests/unit/test_patch_selection.py`

### Implementation for User Story 3

- [X] T038 [US3] Update `_generate_patches` to compute external allowance and internal patch target before bounds generation in `src/reefs/splat/pipeline.py`
- [X] T039 [US3] Pass `internal_patch_target` to `generate_patch_bounds` while preserving final cap for metadata validation in `src/reefs/splat/pipeline.py`
- [X] T040 [US3] Add warnings for internal count exceeding internal target, final cap reached, footprint coverage below `0.25`, and target share within `0.01` of the minimum in `src/reefs/patches/selection.py`
- [X] T041 [US3] Persist `internal_patch_target` and `external_support_allowance` in patch metadata in `src/reefs/patches/export.py`

**Checkpoint**: Patch bounds are sized for internal cameras and final selected sets remain capped.

---

## Phase 6: User Story 4 - Inspect Camera Selection Decisions Before Training (Priority: P2)

**Goal**: Preserve diagnostic filenames while exposing V3 counts, scores, plots, sweep outputs, and known-bad comparisons before LFS training.

**Independent Test**: Run diagnostics-only checks and confirm required CSV/PNG/HTML/log files, sweep folders, summary CSV, review notes, and comparison folders are produced.

### Tests for User Story 4

- [X] T042 [US4] Update diagnostic artefact test for V3 CSV columns and generation log counts in `tests/unit/test_patch_diagnostics.py`
- [X] T043 [US4] Add diagnostic plot category test for kept internal, rejected internal, selected external, and unused external in `tests/unit/test_patch_diagnostics.py`
- [X] T044 [P] [US4] Add metadata export test for V3 diagnostic coverage fields in `tests/unit/test_patch_export.py`

### Implementation for User Story 4

- [X] T045 [US4] Update `camera_coverage.csv` writer with V3 evidence columns in `src/reefs/diagnostics/patch_plots.py`
- [X] T046 [US4] Update `generation.log` writer with V3 counts, settings, derived targets, and warnings in `src/reefs/diagnostics/patch_plots.py`
- [X] T047 [US4] Update static and HTML plots to distinguish V3 camera categories in `src/reefs/diagnostics/patch_plots.py`
- [X] T048 [US4] Update histogram to show V3 target image share or footprint coverage distribution in `src/reefs/diagnostics/patch_plots.py`
- [X] T049 [US4] Add diagnostics-only validation helper for V3 PNG sweeps in `scripts/camera_selection_v3_diagnostics.py`
- [X] T050 [US4] Add known-bad comparison output helper for Dataset 1 p002 and p007 in `scripts/camera_selection_v3_diagnostics.py`
- [X] T051 [US4] Add Polish Town 200-camera first-20-patch validation mode in `scripts/camera_selection_v3_diagnostics.py`
- [X] T052 [US4] Document diagnostics-only validation commands and expected outputs in `specs/009-camera-selection-v3/quickstart.md`

**Checkpoint**: Camera selection can be inspected before LFS training.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final verification, docs hygiene, and repo notes.

- [X] T053 [P] Update selector decision note for V3 in `docs/decisions.md`
- [X] T054 [P] Add troubleshooting note for useful internal camera overflow as patch-bound defect in `docs/troubleshooting.md`
- [X] T055 Run focused unit tests from quickstart in `specs/009-camera-selection-v3/quickstart.md`
- [X] T056 Run full test suite command `uv run pytest -q` from `specs/009-camera-selection-v3/quickstart.md`
- [X] T057 Review public docs for private paths and placeholders in `specs/009-camera-selection-v3/`
- [X] T058 Correct V3 geometry scoring so sparse points are used only for tracks and `footprint_overlap_score`/`target_image_share` come from patch-rectangle/camera-frustum intersection in `src/reefs/patches/selection.py`
- [X] T059 Update Spec Kit docs to record the corrected rectangle/frustum geometry and reject sparse-point-derived footprint scoring in `specs/009-camera-selection-v3/`
- [X] T060 Replace the median-Z projection surface with a local fitted patch plane in `src/reefs/patches/selection.py`
- [X] T061 Update the scratch frustum viewer to render the fitted patch plane for any patch directory
- [X] T062 Update Spec Kit docs to distinguish the raw rectangular patch footprint from the fitted projection plane

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup completion and blocks all user stories.
- **US1 and US2 (P1)**: Depend on Foundational. They touch the same selector file, so implement sequentially unless carefully coordinated.
- **US3 (P2)**: Depends on Foundational and should follow US1/US2 selector target helper work.
- **US4 (P2)**: Depends on V3 evidence records from US1/US2 and metadata fields from US3.
- **Polish**: Depends on desired user stories being complete.

### User Story Dependencies

- **User Story 1**: MVP; no dependency on other user stories.
- **User Story 2**: Depends on the V3 evidence model from User Story 1 but remains independently testable with synthetic support cases.
- **User Story 3**: Depends on target derivation from Foundational and selector cap invariants from User Stories 1 and 2.
- **User Story 4**: Depends on V3 score fields and selected/rejected categories from earlier stories.

### Parallel Opportunities

- Setup config documentation tasks T002-T004 can run in parallel after T001 shape is known.
- Test-writing tasks within each story can run in parallel before implementation.
- Validation/export/diagnostic tests can run in parallel when they touch different files.
- Docs polish tasks T053, T054, and T057 can run in parallel after implementation behaviour is settled.

## Parallel Example: User Story 1

```bash
Task: "T014 [US1] Add synthetic test for useful internal cameras never being replaced by support cameras in tests/unit/test_patch_selection.py"
Task: "T015 [US1] Add synthetic test for unuseful internal cameras being rejected by target image share and evidence rules in tests/unit/test_patch_selection.py"
Task: "T016 [US1] Add synthetic Dataset-1-p002-style internal strip retention test in tests/unit/test_patch_selection.py"
Task: "T017 [US1] Add synthetic Dataset-1-p007-style bend camera retention test in tests/unit/test_patch_selection.py"
```

## Parallel Example: User Story 2

```bash
Task: "T024 [US2] Add test that external_support_fraction = 0 selects only useful internal cameras in tests/unit/test_patch_selection.py"
Task: "T025 [US2] Add test that external candidates come only from one-ring neighbouring patches in tests/unit/test_patch_selection.py"
Task: "T026 [US2] Add test that non-neighbour external cameras are excluded despite good evidence in tests/unit/test_patch_selection.py"
Task: "T027 [US2] Add test that selected external support is capped by external allowance and remaining capacity in tests/unit/test_patch_selection.py"
Task: "T028 [US2] Add test that external ranking balances evidence and azimuth spread in tests/unit/test_patch_selection.py"
```

## Parallel Example: User Story 4

```bash
Task: "T042 [US4] Update diagnostic artefact test for V3 CSV columns and generation log counts in tests/unit/test_patch_diagnostics.py"
Task: "T044 [US4] Add metadata export test for V3 diagnostic coverage fields in tests/unit/test_patch_export.py"
```

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete User Story 1.
3. Run `uv run pytest -q tests/unit/test_patch_selection.py`.
4. Stop and inspect that useful internal cameras are kept before external support exists.

### Incremental Delivery

1. Add US1 internal-first selector behaviour.
2. Add US2 capped neighbouring external support.
3. Add US3 internal-target patch bounds.
4. Add US4 diagnostics and validation helpers.
5. Run focused tests, full tests, then diagnostics-only dataset sweeps.

### Validation Before Training

Do not run LFS training until diagnostic PNG sweeps and known-bad comparisons are reviewed.
