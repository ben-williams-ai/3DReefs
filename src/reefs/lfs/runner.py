"""LichtFeld Studio subprocess runner helpers."""

from __future__ import annotations

import csv
import shutil
import subprocess
import tempfile
from pathlib import Path
from time import perf_counter

from reefs.lfs.commands import build_lfs_train_command
from reefs.lfs.status import LfsProgress, classify_lfs_status, parse_lfs_progress_lines
from reefs.logging.terminal import TerminalReporter
from reefs.logging.timings import utc_now


def _append_log(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)
        if not line.endswith("\n"):
            handle.write("\n")


def _write_loss_history(path: Path, progress: list[LfsProgress]) -> None:
    """Write parsed LFS loss progress as a machine-readable CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["iteration", "requested_iterations", "loss", "splats"])
        for item in progress:
            writer.writerow([item.completed_iterations, item.requested_iterations, item.loss, item.splats])


def _canonicalise_finished_output(status: dict[str, object], output_dir: Path) -> dict[str, object]:
    """Expose a stable output name for completed splats while preserving LFS output."""
    output_file = status.get("output_file")
    if status.get("status") != "complete" or not isinstance(output_file, str):
        return status
    original = Path(output_file)
    alias = output_dir / "splat_finished.ply"
    if alias.exists() or alias.is_symlink():
        alias.unlink()
    alias.symlink_to(original.name)
    return {**status, "original_output_file": str(original), "output_file": str(alias)}


def stage_lfs_dataset(patch_dir: Path, dataset_dir: Path) -> None:
    """Create the minimal directory structure LFS expects for one patch."""
    if dataset_dir.exists():
        shutil.rmtree(dataset_dir)
    dataset_dir.mkdir(parents=True)
    (dataset_dir / "sparse").mkdir()
    (dataset_dir / "sparse" / "0").symlink_to((patch_dir / "sparse" / "0").resolve())
    (dataset_dir / "images").symlink_to((patch_dir / "selected_images").resolve())


def run_lfs_training(
    *,
    lfs_bin: str,
    patch_dir: Path,
    patch_id: str,
    num_iters: int,
    num_splats_per_patch: int,
    strategy: str,
    headless: bool,
    max_width: int | None,
    lfs_config: Path | None,
    lfs_log: Path,
    severe_completion_threshold: float,
    reporter: TerminalReporter | None = None,
) -> dict[str, object]:
    """Run one patch training job with streamed logs."""
    reporter = reporter or TerminalReporter()
    output_dir = patch_dir / "splat"
    output_dir.mkdir(parents=True, exist_ok=True)
    patch_log = output_dir / "run.log"
    started_at = utc_now()
    start = perf_counter()
    with tempfile.TemporaryDirectory(prefix=f"reefs_lfs_{patch_id}_") as temp:
        dataset_dir = Path(temp)
        stage_lfs_dataset(patch_dir, dataset_dir)
        command = build_lfs_train_command(
            lfs_bin=lfs_bin,
            patch_id=patch_id,
            dataset_dir=dataset_dir,
            output_dir=output_dir,
            num_iters=num_iters,
            num_splats_per_patch=num_splats_per_patch,
            strategy=strategy,
            headless=headless,
            max_width=max_width,
            lfs_config=lfs_config,
        )
        header = f"\n## splat.train.{patch_id} | {started_at}\n$ {' '.join(command.args)}\n"
        _append_log(lfs_log, header)
        _append_log(patch_log, header)
        if reporter:
            reporter.info(f"[splat.train.{patch_id}] LFS command starting")
            reporter.info(f"$ {' '.join(command.args)}")
        process = subprocess.Popen(
            command.args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        assert process.stdout is not None
        lines: list[str] = []
        for line in process.stdout:
            stripped = line.rstrip("\n")
            lines.append(stripped)
            _append_log(lfs_log, stripped)
            _append_log(patch_log, stripped)
            if reporter:
                reporter.tee_line(stripped)
        return_code = process.wait()
    ended_at = utc_now()
    duration = round(perf_counter() - start, 6)
    progress = parse_lfs_progress_lines(lines)
    loss_history = output_dir / "loss_history.csv"
    _write_loss_history(loss_history, progress)
    status = classify_lfs_status(
        patch_id=patch_id,
        requested_iterations=num_iters,
        return_code=return_code,
        output_dir=output_dir,
        progress=progress,
        severe_completion_threshold=severe_completion_threshold,
    )
    status = _canonicalise_finished_output(status, output_dir)
    status.update(
        {
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_seconds": duration,
            "log_file": str(patch_log),
            "loss_history_file": str(loss_history),
            "command": command.as_dict(),
        }
    )
    footer = (
        f"[exit_code] {return_code}\n"
        f"[duration_seconds] {duration}\n"
        f"[loss_history_file] {loss_history}\n"
        f"[output_file] {status.get('output_file')}"
    )
    _append_log(lfs_log, footer)
    _append_log(patch_log, footer)
    if reporter:
        reporter.info(f"[splat.train.{patch_id}] LFS finished with exit {return_code} in {duration:.2f}s")
    return status
