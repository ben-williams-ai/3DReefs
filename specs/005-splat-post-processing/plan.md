# Implementation Plan: Splat Cleanup And SOG Compression

**Branch**: `005-splat-post-processing` | **Date**: 2026-06-15 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/005-splat-post-processing/spec.md`

## Summary

Add post-processing stages that take Feature 3 patch training outputs, clean each eligible patch splat, merge the cleaned patch PLYs into one primary site-level cleaned PLY, and export one final SOG by default. The implementation will extend the existing run-record, config, tool-validation, and resume/overwrite machinery while keeping COLMAP, patch generation, LFS training, PlayCanvas, NanoGS, and future LOD work out of scope.

## Technical Context

**Language/Version**: Python 3.12+  
**Primary Dependencies**: Existing `click`, `pydantic`, `pyyaml`, standard library `pathlib/json/subprocess/shutil`; `wildflow` for cleanup and cleaned PLY merge; external `splat-transform` CLI v1.10.2 for final SOG export.  
**Storage**: Filesystem artefacts under Feature 1 run directories, with concise JSON manifests/status/timings and external command logs.  
**Testing**: `pytest` unit and integration tests with mocked wildflow and mocked `splat-transform`; real smoke testing on local completed Feature 3 runs when tools are available.  
**Target Platform**: Ubuntu Linux workstation with existing 3DReefs `uv` environment.  
**Project Type**: Python CLI pipeline.  
**Performance Goals**: Preflight resolves missing tools, missing inputs, existing outputs, and resume/overwrite decisions before heavy work; cleanup runs patch-by-patch; merge and SOG each run once for the site output.  
**Constraints**: Do not modify raw images or Feature 3 training outputs in place; do not call cleanup settings metres; do not silently use raw patch splats when cleaned outputs are expected; avoid duplicative markdown/log reports.  
**Scale/Scope**: Completed reef runs with many patch splats, incomplete patch outputs, and one merged cleaned site splat plus one final SOG.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Reproducible Pipeline Runs**: PASS. The plan reuses the primary `uv` CLI, effective config, CLI overrides, tool versions, and manifests.
- **II. Observable Long-Running Work**: PASS. Cleanup, merge, and SOG stages will record timings, command output, warnings, completion status, and artefact selection.
- **III. Explicit Resume And Overwrite Behaviour**: PASS. Existing cleaned, merged, and SOG outputs are detected and resolved during preflight before any requested post-processing work starts.
- **IV. Modular, Testable Implementation**: PASS. Reusable behaviour will live in `src/reefs/postprocess/` with focused tests for source selection, cleanup, merge, SOG, and resume behaviour.
- **V. External Tool Validation**: PASS. Wildflow cleanup/merge callables and `splat-transform` SOG support are validated up front when requested.
- **VI. Data Safety**: PASS. Raw inputs and training outputs are read-only; public docs/configs use placeholders.

## Project Structure

### Documentation (this feature)

```text
specs/005-splat-post-processing/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── cli.md
│   ├── config-schema.yml
│   ├── post-processing-artifacts.md
│   └── run-records.md
└── tasks.md
```

### Source Code (repository root)

```text
src/reefs/
├── cli.py                         # add post-processing step routing
├── config/
│   └── models.py                  # add cleanup/merge/SOG config models
├── preflight/
│   ├── splat.py                   # extend splat preflight for post-processing
│   └── tools.py                   # validate wildflow and splat-transform
├── run/
│   └── recorder.py                # reuse stage status/timing/log interfaces
└── postprocess/
    ├── __init__.py
    ├── artifacts.py               # source/output discovery and PLY counts
    ├── cleanup.py                 # wildflow cleanup orchestration
    ├── merge.py                   # wildflow cleaned PLY merge orchestration
    ├── pipeline.py                # cleanup -> merge -> SOG orchestration
    ├── resume.py                  # existing output and decision detection
    └── sog.py                     # final SOG export orchestration

tests/
├── integration/
│   ├── test_postprocess_mocked_success.py
│   └── test_postprocess_resume_overwrite.py
└── unit/
    ├── test_postprocess_artifacts.py
    ├── test_postprocess_cleanup.py
    ├── test_postprocess_merge.py
    ├── test_postprocess_sog.py
    └── test_postprocess_validation.py
```

**Structure Decision**: Add a focused `src/reefs/postprocess/` package for reusable post-training behaviour. Keep CLI changes thin and reuse the existing Feature 1 run-record and preflight modules.

## Phase 0: Research Summary

See [research.md](research.md).

Key decisions:

- Use explicit steps `splat.cleanup`, `splat.merge`, `splat.sog`, and `splat.postprocess` rather than changing the current Feature 3 `splat` alias.
- Select `splat_finished.ply` first, otherwise the highest-iteration usable patch PLY, and attach completion severity to every downstream record.
- Preserve the old coral cleanup defaults and semantics by using `wildflow.splat.cleanup_splats` directly.
- Use `wildflow.splat.merge_ply_files` for cleaned PLY merge and `splat-transform` only for final SOG export, with no silent fallback.
- Store one concise post-processing manifest with per-patch cleanup, merge, and SOG sections instead of generating duplicate reports.

## Phase 1: Design Summary

See:

- [data-model.md](data-model.md)
- [contracts/cli.md](contracts/cli.md)
- [contracts/config-schema.yml](contracts/config-schema.yml)
- [contracts/post-processing-artifacts.md](contracts/post-processing-artifacts.md)
- [contracts/run-records.md](contracts/run-records.md)
- [quickstart.md](quickstart.md)

## Post-Design Constitution Check

- **I. Reproducible Pipeline Runs**: PASS. Contracts define config, CLI overrides, tool versions, and post-processing manifest fields.
- **II. Observable Long-Running Work**: PASS. Data model and run-record contract define per-stage timings, warnings, source selection, and final artefact status.
- **III. Explicit Resume And Overwrite Behaviour**: PASS. CLI and run-record contracts require all decisions before work starts.
- **IV. Modular, Testable Implementation**: PASS. Source layout and test layout isolate source selection, cleanup, merge, SOG, and validation.
- **V. External Tool Validation**: PASS. Contracts require up-front validation of wildflow cleanup/merge callables and `splat-transform` SOG support for requested work.
- **VI. Data Safety**: PASS. Artefact contract writes new post-processing outputs only and treats raw images/training outputs as read-only.

## Complexity Tracking

No constitution violations.
