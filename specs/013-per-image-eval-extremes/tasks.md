# Tasks: Per-Image Evaluation Extremes

**Input**: Design documents from `specs/013-per-image-eval-extremes/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Phase 1: Setup

- [x] T001 Create isolated `feature/per-image-eval-extremes` worktree at starting SHA and record it in `specs/013-per-image-eval-extremes/plan.md`
- [x] T002 Confirm `data/patch-results/` is ignored without modifying unrelated main-worktree files
- [x] T003 Generate and validate Spec Kit design artefacts in `specs/013-per-image-eval-extremes/`

---

## Phase 2: Foundational Evidence

- [x] T004 Read all mandated repository references and trace every caller of shared evaluation functions
- [x] T005 Inventory accepted Dataset 1–6 attempts, patch IDs, terminal markers, final PLY counts and final comparison objects into `data/patch-results/inventory/accepted_runs.csv`
- [x] T006 Verify manifests, holdouts, eval sparse inputs, target source, comparison counts and expected bytes in `data/patch-results/inventory/download_manifest.csv`
- [x] T007 Record the per-patch backfill/fallback decision and prove local capacity in `data/patch-results/reports/validation_report.md`

**Checkpoint**: Accepted source evidence is complete before downloads or implementation assumptions.

---

## Phase 3: User Story 1 - Recover Authoritative Per-Image Metrics (Priority: P1)

**Goal**: Produce validated, identity-backed LPIPS/PSNR/SSIM rows from saved composites while preserving aggregate evaluation.

**Independent Test**: Process one synthetic and one real accepted patch; prove identities, counts, metrics, checksums and aggregate reproduction.

- [x] T008 [P] [US1] Add failing per-image/aggregate compatibility tests in `tests/unit/test_eval_image_metrics.py`
- [x] T009 [P] [US1] Add failing sparse-order/index mapping and malformed-input tests in `tests/unit/test_per_image_backfill.py`
- [x] T010 [P] [US1] Add failing six-output/combined-CSV integration test in `tests/integration/test_per_image_backfill.py`
- [x] T011 [US1] Refactor one-pass canonical per-image metric calculation and `per_image_metrics.csv` writing in `src/reefs/eval/image_metrics.py`
- [x] T012 [US1] Preserve LPIPS implementation/public callers and derive legacy aggregates from per-image rows in `src/reefs/eval/lpips.py` and `src/reefs/eval/lfs.py`
- [x] T013 [US1] Implement eval-sparse mapping, provenance validation and atomic score output in `src/reefs/eval/per_image_backfill.py`
- [x] T014 [US1] Add the thin resumable command wrapper in `scripts/backfill_per_image_eval.py`
- [x] T015 [US1] Run focused unit/integration/regression checks and one real canary patch

**Checkpoint**: User Story 1 independently yields canonical image-level scores and matching aggregates.

---

## Phase 4: User Story 2 - Export Deterministic Visual Extremes (Priority: P2)

**Goal**: Export lossless best/worst GT, render and comparison evidence per patch.

**Independent Test**: Repeated export of one patch yields identical selections/checksums and visually correct halves.

- [x] T016 [P] [US2] Add failing deterministic rank/tie/fewer-than-six/export tests in `tests/unit/test_per_image_backfill.py`
- [x] T017 [US2] Implement deterministic selection, safe filenames, lossless split/export and selection checksums in `src/reefs/eval/per_image_backfill.py`
- [x] T018 [US2] Integrate resumable export and validation commands in `scripts/backfill_per_image_eval.py`
- [x] T019 [US2] Visually inspect canary best/worst composites and halves and record results in `data/patch-results/reports/visual_inspection_manifest.json`

**Checkpoint**: User Story 2 independently produces reproducible, visibly valid extremes.

---

## Phase 5: User Story 3 - Audit Complete Six-Dataset Result (Priority: P3)

**Goal**: Download, score, export and validate the complete accepted evidence with durable provenance.

**Independent Test**: Final manifests reproduce every accepted source object, row and extreme selection exactly once.

- [x] T020 [US3] Download and continuously monitor only accepted raw inputs into `data/patch-results/raw/`
- [x] T021 [US3] Run and continuously monitor the complete SHA-256 pass into `data/patch-results/inventory/SHA256SUMS`
- [x] T022 [US3] GPU-score and continuously monitor all accepted comparisons into `data/patch-results/scores/`
- [x] T023 [US3] Validate per-patch aggregate reproduction, combined row counts and uniqueness in `data/patch-results/reports/validation_report.md`
- [x] T024 [US3] Export and continuously monitor all patch extremes into `data/patch-results/extremes/`
- [x] T025 [US3] Inspect best/worst outputs across every dataset and multiple patches in `data/patch-results/reports/visual_inspection_manifest.json`
- [x] T026 [US3] Run final decode/dimension/checksum/raw-immutability validation and complete `data/patch-results/reports/validation_report.md`
- [x] T027 [US3] If and only if required evidence is absent/corrupt, execute and verify the evaluation-only fallback documented in `data/patch-results/reports/validation_report.md`

**Checkpoint**: All accepted Dataset 1–6 evidence is complete and auditable.

---

## Phase 6: Polish, Review And Publication

- [x] T028 Run configured checks, focused/full proportionate pytest and `git diff --check`
- [x] T029 Review Git diff for secrets, data artefacts and unrelated changes
- [x] T030 Mark completed tasks and align `docs/decisions.md` or `docs/troubleshooting.md` only for reusable non-obvious findings
- [ ] T031 Commit and push focused feature changes, merge tested code into `main`, push `main` and verify `origin/main`
- [ ] T032 Verify no generated data is tracked and no unnecessary Nebius VM remains billable
- [ ] T033 Produce the required final report with commits, inventories, counts, tolerances, outputs, warnings and remaining work

## Dependencies & Execution Order

- Phase 1 is complete.
- Phase 2 blocks real downloads and confirms whether fallback work exists.
- US1 blocks US2 and complete scoring; US2 is independently testable after US1.
- US3 uses the verified implementations from US1/US2.
- Publication follows all code and real-data verification.

## Parallel Opportunities

- T008–T010 touch separate test files or cases and can be prepared independently.
- Inventory evidence may be gathered across datasets, but accepted-attempt reconciliation remains deterministic and is reviewed together.
- Full processing is dataset-sequential by default to minimise recovery and GPU complexity.

## Implementation Strategy

The MVP is US1 on one accepted patch. Promote the same verified path to all datasets, add US2 export, then complete US3. No fallback infrastructure is built unless inventory proves it necessary.
