# Tasks: Run Resume Hardening

- [x] Add `--run-id` CLI option.
- [x] Allow run paths to reuse an existing run directory.
- [x] Create durable run recorder for immediate manifest/status/timing writes.
- [x] Add per-stage status and active-command metadata.
- [x] Update CLI to write initial records before tool validation.
- [x] Update CLI to persist status after foundation and SfM substages.
- [x] Avoid reporting `sfm.preflight` as full `sfm` completion.
- [x] Add SfM filesystem inspection for missing or incomplete records.
- [x] Reuse selected sparse outputs from the same run dir for `sfm.undistort`.
- [x] Remove partial undistortion output before overwrite reruns.
- [x] Stream COLMAP command output to `logs/colmap.log`.
- [x] Add tests for explicit SfM stage-boundary reruns and missing prerequisites.
- [x] Update Feature 1 and Feature 2 run-record contracts.
- [x] Update README and repo decision/troubleshooting notes.
- [x] Add focused unit and integration tests.
