# Implementation Plan: Run Resume Hardening

**Branch**: `004-run-resume-hardening`

## Scope

Harden the existing Feature 1/2 run-record and resume machinery. This feature
does not add new scientific pipeline stages; it makes existing and future stages
safe to resume after interruption.

## Technical Approach

- Add `--run-id` to the main CLI.
- Reuse an existing run directory when `--run-id` is supplied or resume
  discovery identifies exactly one prior run to resume or overwrite.
- Add a durable `RunRecorder` that writes canonical records at run start and
  persists status/timing changes after stages.
- Extend `run_status.json` with per-stage state and active command metadata.
- Seed status from SfM filesystem outputs when resuming older runs with missing
  or incomplete records.
- Stream COLMAP command output incrementally to `logs/colmap.log`.
- For `sfm.undistort --resume-policy overwrite`, remove the generated partial
  `sfm/undistorted/` output before rerunning undistortion in the same run dir.

## Validation

- Unit tests cover missing-record filesystem detection.
- Integration tests cover run-id reuse, preflight-only status, and undistort
  overwrite in an existing run.
- Existing foundation and mocked SfM tests continue to pass.
