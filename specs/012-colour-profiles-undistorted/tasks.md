# Tasks: Dataset-Specific Undistorted Colour Profiles

## Phase 1: Setup

- [x] T001 Update Spec Kit active plan reference in AGENTS.md

## Phase 2: Foundation

- [x] T002 Add failing profile/config tests in tests/unit/test_colour_profiles.py and tests/unit/test_config_models.py
- [x] T003 Add profile schema, fingerprint, serialisation and validation in src/reefs/colour/profile.py
- [x] T004 Add profile mode/path validation and config-relative resolution in src/reefs/config/models.py and src/reefs/config/loader.py

## Phase 3: User Story 1 - Safe undistorted colour training

- [x] T005 [US1] Add corrected-undistorted workspace application tests in tests/integration/test_colour_undistorted.py
- [x] T006 [US1] Implement atomic corrected workspace application in src/reefs/colour/pipeline.py
- [x] T007 [US1] Select only matching undistorted/corrected image and sparse workspaces in src/reefs/splat/validation.py and src/reefs/cli.py
- [x] T008 [US1] Preserve exact off-mode behaviour and reject legacy recoloured splat inputs in tests/integration/test_colour_disabled_pipeline.py

## Phase 4: User Story 2 - Save GUI profile

- [x] T009 [US2] Add profile persistence/interpolation round-trip tests in tests/unit/test_colour_profiles.py and tests/unit/test_colour_interpolation.py
- [x] T010 [US2] Add profile create CLI and GUI save integration in src/reefs/cli.py and src/reefs/colour/gui.py
- [x] T011 [US2] Persist and consume exact SfM staging maps in src/reefs/sfm/pipeline.py

## Phase 5: User Story 3 - Nebius

- [x] T012 [US3] Carry mapping/profile provenance in src/reefs/experiments/ablations/source_bundle.py
- [x] T013 [US3] Add optional verified profile download/configuration in scripts/nebius/run_ablation_worker.sh
- [x] T014 [US3] Correct selected training and full-resolution evaluation workspaces in the Stage 2 path

## Phase 6: Polish

- [x] T015 Update configs/example.yml, README.MD, docs/decisions.md and docs/troubleshooting.md
- [x] T016 Run focused and full tests plus shell syntax checks, then mark all tasks complete
