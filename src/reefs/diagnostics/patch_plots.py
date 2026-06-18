"""Non-interactive patch and camera-pose diagnostic plots."""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from reefs.patches.artefacts import SparseImage, SparseScene
from reefs.patches.bounds import PatchBounds
from reefs.patches.outliers import OutlierFilterResult
from reefs.patches.selection import CameraSelectionScore, PatchSelection


_CATEGORY_STYLE = {
    "kept_internal": {"label": "Kept internal", "colour": "#1f77b4", "fill": "#1f77b4", "zorder": 4},
    "rejected_internal": {"label": "Rejected internal", "colour": "#1f77b4", "fill": "none", "zorder": 1},
    "selected_external": {"label": "Selected external", "colour": "#d62728", "fill": "#d62728", "zorder": 4},
    "unused_external": {"label": "Unused external", "colour": "#f7b6d2", "fill": "none", "zorder": 3},
}


def _equal_xy_limits(xs: list[float], ys: list[float]) -> tuple[float, float, float, float]:
    if not xs or not ys:
        return -1.0, 1.0, -1.0, 1.0
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span = max(max_x - min_x, max_y - min_y, 1e-6)
    centre_x = (min_x + max_x) / 2.0
    centre_y = (min_y + max_y) / 2.0
    padding = span * 0.08
    half = (span / 2.0) + padding
    return centre_x - half, centre_x + half, centre_y - half, centre_y + half


def _camera_source_label(image: SparseImage) -> str:
    parts = Path(image.name).parts
    return parts[0] if len(parts) > 1 else "single"


def _selection_categories(selection: PatchSelection) -> dict[str, list[CameraSelectionScore]]:
    return {
        "kept_internal": [score for score in selection.camera_scores if score.selection_role == "kept_internal"],
        "rejected_internal": [score for score in selection.camera_scores if score.selection_role == "rejected_internal"],
        "selected_external": [score for score in selection.camera_scores if score.selection_role == "selected_external"],
        "unused_external": [score for score in selection.camera_scores if score.selection_role == "unused_external"],
    }


def _draw_patch_rect(axis, bounds: PatchBounds, *, colour: str, linestyle: str = "-", linewidth: float = 1.5) -> None:
    axis.add_patch(
        plt.Rectangle(
            (bounds.min_x, bounds.min_y),
            bounds.width,
            bounds.height,
            fill=False,
            edgecolor=colour,
            linestyle=linestyle,
            linewidth=linewidth,
        )
    )
    axis.text(*bounds.centre, bounds.patch_id, color=colour, ha="center", va="center", fontsize=8)


def _write_selection_html(path: Path, selection: PatchSelection, categories: dict[str, list[CameraSelectionScore]]) -> None:
    """Write a lightweight self-contained HTML diagnostic."""
    rows = []
    for category_name in ["kept_internal", "rejected_internal", "selected_external", "unused_external"]:
        for score in categories[category_name]:
            rows.append(
                "<tr>"
                f"<td>{category_name}</td><td>{score.image_name}</td><td>{score.pool}</td>"
                f"<td>{score.source_patch}</td><td>{score.visible_patch_track_count}</td>"
                f"<td>{score.footprint_overlap_score:.6f}</td>"
                f"<td>{score.target_image_share:.6f}</td><td>{score.external_score:.6f}</td>"
                f"<td>{score.azimuth_sector}</td>"
                "</tr>"
            )
    path.write_text(
        "\n".join(
            [
                "<!doctype html><html><head><meta charset='utf-8'>",
                f"<title>{selection.bounds.patch_id} camera selection</title>",
                "<style>body{font-family:sans-serif}table{border-collapse:collapse}"
                "td,th{border:1px solid #ddd;padding:4px 6px;font-size:12px}</style>",
                "</head><body>",
                f"<h1>{selection.bounds.patch_id} camera selection</h1>",
                "<p>Open plot.png for the spatial view. This table mirrors the CSV ranking fields.</p>",
                "<table><thead><tr><th>category</th><th>image</th><th>pool</th><th>source patch</th>"
                "<th>patch tracks</th><th>footprint overlap</th><th>target image share</th>"
                "<th>external score</th><th>sector</th></tr></thead><tbody>",
                *rows,
                "</tbody></table></body></html>",
            ]
        ),
        encoding="utf-8",
    )


def write_patch_summary(scene: SparseScene, bounds: list[PatchBounds], output_path: Path) -> list[str]:
    """Write a run-level camera-position and patch-boundary summary plot."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    try:
        labels = sorted({_camera_source_label(image) for image in scene.images})
        palette = plt.get_cmap("tab10")
        colours = {label: palette(index % 10) for index, label in enumerate(labels)}
        fig, axis = plt.subplots(figsize=(10, 10))
        for label in labels:
            images = [image for image in scene.images if _camera_source_label(image) == label]
            axis.scatter(
                [image.center[0] for image in images],
                [image.center[1] for image in images],
                s=8,
                color=colours[label],
                label=label,
                alpha=0.75,
            )
        for patch_bounds in bounds:
            _draw_patch_rect(axis, patch_bounds, colour="#222222", linewidth=1.2)
        xs = [image.center[0] for image in scene.images]
        ys = [image.center[1] for image in scene.images]
        for patch_bounds in bounds:
            xs.extend([patch_bounds.min_x, patch_bounds.max_x])
            ys.extend([patch_bounds.min_y, patch_bounds.max_y])
        axis.set_xlim(*_equal_xy_limits(xs, ys)[:2])
        axis.set_ylim(*_equal_xy_limits(xs, ys)[2:])
        axis.set_aspect("equal", adjustable="box")
        axis.set_xlabel("scene x")
        axis.set_ylabel("scene y")
        axis.set_title("Patch summary")
        axis.grid(True, alpha=0.25)
        axis.legend(loc="upper right")
        fig.tight_layout()
        fig.savefig(output_path, dpi=180)
        plt.close(fig)
    except Exception as exc:  # pragma: no cover - backend failures are environment-specific.
        warnings.append(f"patch summary plot failed: {exc}")
    return warnings


def write_patch_selection_diagnostics(selection: PatchSelection, diagnostics_dir: Path) -> list[str]:
    """Write old-style CSV/log/plot diagnostics for one patch."""
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    categories = _selection_categories(selection)
    csv_path = diagnostics_dir / "camera_coverage.csv"
    fieldnames = [
        "image_name",
        "selection_role",
        "pool",
        "source_patch",
        "visible_patch_track_count",
        "normalised_track_score",
        "footprint_overlap_score",
        "target_image_share",
        "external_evidence_score",
        "azimuth_degrees",
        "azimuth_spread_score",
        "external_score",
        "azimuth_sector",
        "camera_x",
        "camera_y",
        "camera_z",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for score in sorted(selection.camera_scores, key=lambda item: item.ranking_tuple()):
            row = score.as_dict()
            writer.writerow({field: row[field] for field in fieldnames})

    log_lines = [
        f"patch_id: {selection.bounds.patch_id}",
        f"max_cameras: {selection.max_cameras}",
        f"external_support_fraction: {selection.external_support_fraction:.2f}",
        f"external_support_allowance: {selection.external_support_allowance}",
        f"internal_patch_target: {selection.internal_patch_target}",
        f"selected_camera_count: {len(selection.selected_images)}",
        f"selected_internal_count: {len(categories['kept_internal'])}",
        f"rejected_internal_count: {len(categories['rejected_internal'])}",
        f"selected_external_count: {len(categories['selected_external'])}",
        f"unused_external_count: {len(categories['unused_external'])}",
        f"patch_footprint_coverage: {selection.patch_footprint_coverage:.6f}",
        f"target_image_share_min: {selection.coverage_summary()['target_image_share_min']:.6f}",
        f"target_image_share_median: {selection.coverage_summary()['target_image_share_median']:.6f}",
        f"sparse_point_count: {len(selection.patch_points)}",
        *[f"warning: {warning}" for warning in selection.warnings],
    ]
    (diagnostics_dir / "generation.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    try:
        _write_selection_html(diagnostics_dir / "plot.html", selection, categories)
        fig, axis = plt.subplots(figsize=(10, 10))
        _draw_patch_rect(axis, selection.bounds, colour="#2ca02c", linewidth=2.0)
        for neighbour in selection.neighbour_bounds:
            _draw_patch_rect(axis, neighbour, colour="#7f7f7f", linestyle=":", linewidth=1.0)
        xs = [selection.bounds.min_x, selection.bounds.max_x]
        ys = [selection.bounds.min_y, selection.bounds.max_y]
        for neighbour in selection.neighbour_bounds:
            xs.extend([neighbour.min_x, neighbour.max_x])
            ys.extend([neighbour.min_y, neighbour.max_y])
        for category_name in ["rejected_internal", "unused_external", "kept_internal", "selected_external"]:
            scores = categories[category_name]
            if not scores:
                continue
            style = _CATEGORY_STYLE[category_name]
            xs.extend(score.camera_x for score in scores)
            ys.extend(score.camera_y for score in scores)
            axis.scatter(
                [score.camera_x for score in scores],
                [score.camera_y for score in scores],
                s=28,
                c=style["fill"],
                edgecolors=style["colour"] if style["fill"] == "none" else "black",
                linewidths=1.1 if style["fill"] == "none" else 0.3,
                label=style["label"],
                zorder=style["zorder"],
            )
        x_min, x_max, y_min, y_max = _equal_xy_limits(xs, ys)
        axis.set_xlim(x_min, x_max)
        axis.set_ylim(y_min, y_max)
        axis.set_aspect("equal", adjustable="box")
        axis.set_xlabel("scene x")
        axis.set_ylabel("scene y")
        axis.set_title(f"{selection.bounds.patch_id} camera selection")
        axis.grid(True, alpha=0.25)
        axis.legend(loc="upper right")
        fig.tight_layout()
        fig.savefig(diagnostics_dir / "plot.png", dpi=180)
        plt.close(fig)
    except Exception as exc:  # pragma: no cover - plot backend failures are environment-specific.
        warnings.append(f"selection plot failed: {exc}")

    try:
        selected_values = [score.target_image_share for score in selection.camera_scores if score.selected]
        unselected_values = [score.target_image_share for score in selection.camera_scores if not score.selected]
        fig, axis = plt.subplots(figsize=(10, 5.5))
        axis.hist(unselected_values, bins=20, color="#f7b6d2", edgecolor="#f4a3c4", alpha=0.7, label=f"Unselected ({len(unselected_values)})")
        axis.hist(selected_values, bins=20, color="#1f77b4", edgecolor="#174f7a", alpha=0.7, label=f"Selected ({len(selected_values)})")
        axis.set_title(f"{selection.bounds.patch_id} target image share")
        axis.set_xlabel("Target image share")
        axis.set_ylabel("Number of images")
        axis.grid(True, alpha=0.25)
        axis.legend(loc="upper right")
        fig.tight_layout()
        fig.savefig(diagnostics_dir / "histogram.png", dpi=180)
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
