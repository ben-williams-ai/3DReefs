# Research: Live Terminal Output

## Decision: Tee Existing Output Instead Of Building Progress Bars

**Rationale**: COLMAP, LFS, and splat-transform already emit useful progress. The current problem is that the pipeline captures that output and writes it only to files. A tee keeps behaviour familiar and avoids fragile estimated progress.

**Alternatives considered**: Custom progress bars and percentage estimates. Rejected because stage durations vary heavily by dataset and tool internals.

## Decision: Print Stage Transitions From RunRecorder

**Rationale**: Stage state already flows through `RunRecorder`. Printing there avoids scattering start/finish messages across every caller and keeps terminal messages aligned with persisted status.

**Alternatives considered**: Add separate print calls beside every `stage_started` call. Rejected because it would drift.

## Decision: Add Only Coarse Internal Progress

**Rationale**: Python-only stages like outlier filtering and patch generation can be silent. Coarse messages are enough to show the run is alive without adding fragile inner-loop progress.

**Alternatives considered**: Fine-grained per-camera or per-point progress. Rejected as noisy and likely to slow large runs.
