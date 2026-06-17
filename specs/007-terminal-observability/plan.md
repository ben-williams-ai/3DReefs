# Implementation Plan: Live Terminal Output

**Branch**: `007-terminal-observability` | **Date**: 2026-06-17 | **Spec**: `specs/007-terminal-observability/spec.md`
**Input**: Feature specification from `specs/007-terminal-observability/spec.md`

## Summary

Add one small terminal reporting path that prints stage progress and tees external command output to stdout while keeping the existing log files and run records unchanged in purpose.

## Technical Context

**Language/Version**: Python 3.13  
**Primary Dependencies**: click, pytest, existing COLMAP/LFS/splat-transform subprocess runners  
**Storage**: Existing JSON/YAML run records and text logs  
**Testing**: pytest  
**Target Platform**: Linux CLI  
**Project Type**: Python CLI pipeline  
**Performance Goals**: No meaningful overhead beyond writing existing output to stdout  
**Constraints**: Do not add progress bars, config switches, or new dependencies  
**Scale/Scope**: Full 3DReefs pipeline stages from preflight through SOG

## Constitution Check

- **I. Reproducible Pipeline Runs**: Pass. Existing run records remain the durable source of truth.
- **II. Observable Long-Running Work**: Pass. This feature directly improves live observability while preserving logs.
- **III. Explicit Resume And Overwrite Behaviour**: Pass. No new prompts or overwrite decisions are introduced.
- **IV. Modular, Testable Implementation**: Pass. Add a small reusable reporting helper and focused tests.
- **V. External Tool Validation**: Pass. Tool validation behaviour is unchanged.
- **VI. Data Safety**: Pass. No raw image mutation or public private paths.

## Project Structure

### Documentation

```text
specs/007-terminal-observability/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── terminal-output.md
└── tasks.md
```

### Source Code

```text
src/reefs/
├── logging/
│   ├── run_logger.py
│   └── terminal.py
├── runs/
│   └── recorder.py
├── colmap/runner.py
├── lfs/runner.py
├── postprocess/sog.py
├── postprocess/pipeline.py
├── sfm/pipeline.py
├── splat/pipeline.py
└── cli.py

tests/
├── unit/
│   └── test_terminal_output.py
└── integration/
    └── test_terminal_observability.py
```

**Structure Decision**: Keep CLI thin. Put terminal-specific behaviour in `src/reefs/logging/terminal.py`; wire existing orchestration and runner code through it.

## Research

See `research.md`.

## Implementation Notes

- Add a `TerminalReporter` with `info`, `stage_started`, `stage_completed`, `stage_failed`, and `tee_line`.
- Let `RunRecorder` optionally hold a reporter and logger so status transitions also print and append to `pipeline.log`.
- Mirror subprocess output by printing each captured line as it is written to logs.
- Add coarse messages around long internal splat/postprocess loops, including per-patch camera selection, selected counts, patch dataset export, diagnostic writing, and validation status during `splat.patch`.
- Preserve existing log files; do not replace them with terminal output.

## Post-Design Constitution Check

Pass. The design adds observability without changing resume, config, data safety, or tool selection semantics.
