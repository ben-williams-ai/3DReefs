"""Non-interactive patch and camera-pose diagnostic plots."""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from reefs.patches.selection import PatchSelection
from reefs.patches.outliers import OutlierFilterResult


def write_patch_selection_diagnostics(selection: PatchSelection, diagnostics_dir: Path) -> list[str]:
    """Write required CSV/log and best-effort PNG diagnostics for one patch."""
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    csv_path = diagnostics_dir / "camera_coverage.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "image_id",
                "image_name",
                "local",
                "visible_patch_points",
                "total_visible_points",
                "score",
                "selected",
            ],
        )
        writer.writeheader()
        for row in selection.camera_scores:
            writer.writerow(row.as_dict())

    log_lines = [
        f"patch_id: {selection.bounds.patch_id}",
        f"selected_camera_count: {len(selection.selected_images)}",
        f"sparse_point_count: {len(selection.patch_points)}",
        *[f"warning: {warning}" for warning in selection.warnings],
    ]
    (diagnostics_dir / "generation.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    try:
        selected_ids = {image.image_id for image in selection.selected_images}
        fig, axis = plt.subplots(figsize=(6, 4))
        for image in selection.local_images:
            axis.scatter(image.center[0], image.center[1], c="tab:blue", s=20)
        for image in selection.selected_images:
            axis.scatter(
                image.center[0],
                image.center[1],
                c="tab:orange" if image.image_id in selected_ids else "tab:gray",
                s=30,
            )
        axis.set_title(selection.bounds.patch_id)
        axis.set_xlabel("scene x")
        axis.set_ylabel("scene y")
        fig.tight_layout()
        fig.savefig(diagnostics_dir / "selection_plot.png", dpi=150)
        plt.close(fig)
    except Exception as exc:  # pragma: no cover - plot backend failures are environment-specific.
        warnings.append(f"selection plot failed: {exc}")

    try:
        fig, axis = plt.subplots(figsize=(6, 4))
        axis.hist([score.visible_patch_points for score in selection.camera_scores], bins=10)
        axis.set_xlabel("visible patch points")
        axis.set_ylabel("camera count")
        fig.tight_layout()
        fig.savefig(diagnostics_dir / "coverage_histogram.png", dpi=150)
        plt.close(fig)
    except Exception as exc:  # pragma: no cover - plot backend failures are environment-specific.
        warnings.append(f"coverage histogram failed: {exc}")
    return warnings


def write_outlier_pose_diagnostics(result: OutlierFilterResult, diagnostics_dir: Path) -> list[str]:
    """Write before/after top and side camera-pose diagnostics."""
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    records = result.records
    if not records:
        return warnings
    kept = [record for record in records if record.decision != "removed"]
    before_sets = [(records, "camera_pose_top_before.png", (0, 1)), (records, "camera_pose_side_before.png", (0, 2))]
    after_sets = [(kept, "camera_pose_top_after.png", (0, 1)), (kept, "camera_pose_side_after.png", (0, 2))]
    for plot_records, filename, axes in [*before_sets, *after_sets]:
        try:
            fig, axis = plt.subplots(figsize=(6, 4))
            for record in plot_records:
                colour = "tab:red" if record.decision in {"removed", "proposed"} else "tab:blue"
                axis.scatter(record.camera_center[axes[0]], record.camera_center[axes[1]], c=colour, s=16)
            axis.set_xlabel(f"scene {'xyz'[axes[0]]}")
            axis.set_ylabel(f"scene {'xyz'[axes[1]]}")
            axis.set_title(filename.replace("_", " ").replace(".png", ""))
            fig.tight_layout()
            fig.savefig(diagnostics_dir / filename, dpi=150)
            plt.close(fig)
        except Exception as exc:  # pragma: no cover - backend failures are environment-specific.
            warnings.append(f"{filename} failed: {exc}")
    return warnings
