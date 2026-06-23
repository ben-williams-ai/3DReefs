# Implementation Plan: Optional Image Recolour Workflow

**Branch**: `010-image-recolour-workflow` | **Date**: 2026-06-22 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/010-image-recolour-workflow/spec.md`

## Summary

Add an optional, resumable colour restoration workflow that starts after normal preflight, lets users tune Wildflow-style colour parameters on ordered keyframes, writes full-resolution corrected images beside `raw_images`, and makes those corrected images available only as splatting-stage image inputs/review assets. SfM feature extraction, matching, reconstruction, and COLMAP undistortion remain based on raw images. The implementation will add a shared image-ordering module, a `reefs.colour` package for filter application, keyframe/state management, and the desktop GUI, plus CLI integration for pipeline-driven and standalone colour restoration. Splat validation paths will be extended so splatting waits whenever required colour correction is incomplete or an active colour session is in progress.

## Technical Context

**Language/Version**: Python >=3.12  
**Primary Dependencies**: Existing `click`, `pydantic`, `pyyaml`, `pycolmap`, `wildflow`; add `PySide6` for the GUI and explicit image/filter dependencies needed for Wildflow-style processing (`torch`, `numpy`, `Pillow`) if they are not already direct project dependencies.  
**Storage**: Files under project/run directories: corrected images in `recoloured_images/`; colour state JSON in `<project.dir>/runs/<run_id>/colour_restoration/`; existing run manifest/status/timings/log files.  
**Testing**: `uv run pytest` with focused unit and integration tests under `tests/unit/` and `tests/integration/`; GUI logic tested through state/model/controller units with minimal smoke coverage for opening where environment permits.  
**Target Platform**: Ubuntu/Linux workstation with local filesystem image datasets; graphical desktop session required only when opening the colour GUI.  
**Project Type**: Python CLI pipeline with desktop GUI workflow and external COLMAP/LFS tool integration.  
**Performance Goals**: Process full-resolution images in batches with visible progress; avoid final-output processing from GUI preview thumbnails; maintain existing non-recolour pipeline runtime when `project.recolour_images` is false.  
**Constraints**: Never modify raw images; preserve relative paths, filenames, extensions where possible, and dimensions; fail early if colour GUI cannot open when required; require explicit warning/confirmation before overwriting an existing corrected image set; always use raw images for SfM feature extraction, matching, reconstruction, and COLMAP undistortion; use corrected images only for splatting-stage image inputs/review when colour state is complete.  
**Scale/Scope**: Single- and multi-camera datasets from hundreds to tens of thousands of images; default 10 keyframes globally or per camera; supports reopened and standalone colour sessions for one run at a time.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Reproducible Pipeline Runs**: PASS. Plan records colour state, effective paths, config values, ordering method, active/completion state, and corrected-output decisions in run artefacts.
- **II. Observable Long-Running Work**: PASS. Plan requires progress counters, terminal/log output, timings/status updates, and failure records for colour correction and waiting states.
- **III. Explicit Resume And Overwrite Behaviour**: PASS WITH DESIGN CONSTRAINT. Existing corrected images may only be overwritten after an explicit warning/confirmation; preflight detects reusable/partial state where possible, while GUI-driven apply prompts handle user-initiated reapply decisions.
- **IV. Modular, Testable Implementation**: PASS. New behaviour is planned as importable modules under `src/reefs/colour/` plus thin CLI hooks and focused tests.
- **V. External Tool Validation**: PASS. Existing COLMAP/LFS validation remains; colour acceleration is detected and reported without silently changing required outputs.
- **VI. Data Safety**: PASS. Raw images are read-only inputs; public docs use placeholders and no private paths.

## Project Structure

### Documentation (this feature)

```text
specs/010-image-recolour-workflow/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── cli.md
│   └── colour-state.schema.json
└── tasks.md
```

### Source Code (repository root)

```text
src/reefs/
├── colour/
│   ├── __init__.py
│   ├── filters.py
│   ├── gui.py
│   ├── interpolation.py
│   ├── ordering.py
│   ├── pipeline.py
│   └── state.py
├── cli.py
├── config/models.py
├── io/paths.py
├── preflight/images.py
├── sfm/pipeline.py
├── sfm/validation.py
├── splat/pipeline.py
└── splat/validation.py

tests/
├── unit/
│   ├── test_colour_filters.py
│   ├── test_colour_interpolation.py
│   ├── test_colour_ordering.py
│   ├── test_colour_state.py
│   └── test_image_layout.py
└── integration/
    ├── test_colour_cli.py
    ├── test_colour_pipeline_resume.py
    ├── test_sfm_recoloured_undistortion.py
    └── test_splat_colour_wait.py

README.MD
configs/example.yml
configs/datasets/*.yml
```

**Structure Decision**: Keep the existing single Python package layout. Add reusable colour restoration domain logic under `src/reefs/colour/`; keep CLI and pipeline layers thin; keep SfM/COLMAP undistortion raw-only; extend splat validation and input selection rather than creating a separate COLMAP handoff.

## Phase 0: Research

See [research.md](research.md). All technical unknowns are resolved there; no `NEEDS CLARIFICATION` items remain.

## Phase 1: Design And Contracts

- Data model: [data-model.md](data-model.md)
- CLI contract: [contracts/cli.md](contracts/cli.md)
- State contract: [contracts/colour-state.schema.json](contracts/colour-state.schema.json)
- Quickstart: [quickstart.md](quickstart.md)

## Constitution Check (Post-Design)

- **I. Reproducible Pipeline Runs**: PASS. `ColourRestorationState` and contracts include config, paths, ordering, status, and source/output roots.
- **II. Observable Long-Running Work**: PASS. Research and contracts require progress, logs, status, and explicit wait messages.
- **III. Explicit Resume And Overwrite Behaviour**: PASS. State machine and CLI contract require resume detection and overwrite warning before replacing corrected outputs.
- **IV. Modular, Testable Implementation**: PASS. Data model maps to importable `reefs.colour` modules and focused tests.
- **V. External Tool Validation**: PASS. Plan keeps existing external tool validation and adds colour processing device detection/reporting.
- **VI. Data Safety**: PASS. Data model and contracts forbid raw image mutation and require mirrored corrected outputs.

## Complexity Tracking

No constitution violations require justification.
