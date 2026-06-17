# Data Model: Live Terminal Output

## TerminalEvent

- `level`: informational, warning, or error.
- `message`: human-readable text shown immediately to the terminal.
- `stage`: optional pipeline stage name.
- `elapsed_seconds`: optional elapsed time for completed stages.

## StageStatusEvent

- `stage`: pipeline stage name.
- `state`: started, complete, failed, skipped, or interrupted.
- `timestamp`: event time.
- `message`: concise user-facing summary.

## ToolOutputLine

- `tool`: COLMAP, LFS, or splat-transform.
- `stage`: pipeline stage associated with the command.
- `line`: output text mirrored to terminal and log.
