# LFS Training Contract

## Dataset Staging

For each valid patch, the pipeline prepares an LFS-compatible temporary dataset:

```text
<temp>/
  sparse/0/      # symlink or copy of patch sparse/0
  images/        # symlinks to selected undistorted images
```

Required behaviour:
- The temporary dataset includes only images selected for the patch.
- The original undistorted images are not modified.
- Temporary files are cleaned up after the patch job unless debug retention is
  explicitly enabled in a later plan/task.

## Command Semantics

The LFS command is constructed from:
- `tools.lfs_bin`
- patch temporary dataset path
- patch output directory
- optional LFS config profile
- `headless`
- optional `max_width`
- `num_iters`
- `num_splats_per_patch`
- `strategy`

Required behaviour:
- Exactly one LFS process runs at a time from this pipeline process.
- Per-patch stdout/stderr is streamed to the patch log and global `logs/lfs.log`.
- Parsed loss progress is written to a per-patch `loss_history.csv` with
  iteration, requested iteration count, loss, and splat count.
- Return code, duration, parsed progress, loss history path, final output path,
  and warnings are recorded for each patch.

## Progress Parsing

The runner should parse progress lines containing:

```text
<completed>/<requested> | Loss: <loss> | Splats: <count>
```

If LFS changes this format, the patch status must still record process return
code, output artefact presence, and a warning that progress parsing failed.

The raw LFS logs remain terminal-style logs. The CSV loss history is the stable
machine-readable loss record for plotting or later analysis.

## Output Naming

LFS may write iteration-stamped files such as `splat_30000.ply`. For a completed
training run, the pipeline exposes `splat_finished.ply` as the stable completed
output and preserves the original iteration-stamped file. For usable incomplete
outputs, the pipeline keeps the iteration-stamped output path so the filename
communicates the completed iteration count.

## Status Classification

Statuses:
- `complete`: completed requested iterations and expected output exists.
- `warning`: completed at least 80 percent but less than 100 percent.
- `severe_warning`: completed less than 80 percent but produced a usable partial
  output.
- `failed`: no usable output or startup/runtime failure.
- `skipped`: requested patch was invalid before training.
- `not_requested`: patch existed but was not in the requested patch list.

Required behaviour:
- Automatic retraining is disabled by default.
- Explicit retraining may target missing, failed, or incomplete patches.
- Patch status is written even when LFS fails.
