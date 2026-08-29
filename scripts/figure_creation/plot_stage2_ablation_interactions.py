#!/usr/bin/env python3
"""Plot Stage 2 3DGS interactions from the authoritative results table."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "experiments/results/stage2/stage2_results.csv"
AUDIT_INPUT = ROOT / "experiments/results/stage2/stage2_all_results.csv"
OUTPUT_DIR = ROOT / "experiments/results/stage2"
RESOLUTIONS = ("1024", "2048", "full")
CAMERAS_PER_PATCH = ("200", "400", "800")
GAUSSIAN_BUDGETS = ("500000", "1000000", "2000000")
METRICS = (
    ("lpips", "LPIPS ↓"),
    ("ssim", "SSIM ↑"),
    ("psnr", "PSNR (dB) ↑"),
)
MINIMUM_PATCH_COMPLETION = 0.9


def load_cells() -> dict[tuple[str, str, str, str], dict[str, float]]:
    """Return patch-averaged, fully completed dataset/configuration cells."""
    with INPUT.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    failures = [row for row in rows if row["status"] != "COMPLETE"]
    if failures:
        raise ValueError(
            f"{INPUT} is not the success-only master: {len(failures)} non-complete rows"
        )
    keys = [
        (
            row["dataset_id"],
            row["training_resolution"],
            row["patch_size"],
            row["gaussian_limit"],
            row["patch_id"],
        )
        for row in rows
    ]
    if len(keys) != len(set(keys)):
        raise ValueError(f"{INPUT} contains duplicate scientific rows")

    grouped: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[
            (
                row["dataset_id"],
                row["training_resolution"],
                row["patch_size"],
                row["gaussian_limit"],
            )
        ].append(row)

    cells = {}
    for key, cell_rows in grouped.items():
        cells[key] = {
            metric: float(np.mean([float(row[metric]) for row in cell_rows]))
            for metric, _ in METRICS
        }
    return cells


def load_undertrained_configs() -> set[tuple[str, str, str]]:
    """Return configurations with any dataset probe below 90% completion."""
    with AUDIT_INPUT.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    grouped: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[
            (
                row["dataset_id"],
                row["training_resolution"],
                row["patch_size"],
                row["gaussian_limit"],
            )
        ].append(row)
    return {
        key[1:]
        for key, probe_rows in grouped.items()
        if sum(row["status"] == "COMPLETE" for row in probe_rows) / len(probe_rows)
        < MINIMUM_PATCH_COMPLETION
    }


def save_interactions(
    cells: dict[tuple[str, str, str, str], dict[str, float]],
    undertrained_configs: set[tuple[str, str, str]],
    metrics: tuple[tuple[str, str], ...],
    output: Path,
    figure_size: tuple[float, float],
) -> None:
    """Plot resolution and Gaussian-budget interactions by camera count."""
    colours = plt.rcParams["axes.prop_cycle"].by_key()["color"][:3]
    fig, raw_axes = plt.subplots(
        len(metrics),
        3,
        figsize=figure_size,
        sharex=True,
        sharey="row",
        squeeze=False,
    )
    x = np.arange(3)

    for row_index, (metric, metric_label) in enumerate(metrics):
        for column_index, camera_count in enumerate(CAMERAS_PER_PATCH):
            ax = raw_axes[row_index, column_index]
            for gaussian_index, (budget, colour) in enumerate(
                zip(GAUSSIAN_BUDGETS, colours)
            ):
                means, standard_deviations = [], []
                for resolution in RESOLUTIONS:
                    values = [
                        value[metric]
                        for (
                            _,
                            cell_resolution,
                            cell_camera_count,
                            cell_budget,
                        ), value in cells.items()
                        if cell_resolution == resolution
                        and cell_camera_count == camera_count
                        and cell_budget == budget
                    ]
                    means.append(float(np.mean(values)))
                    standard_deviations.append(float(np.std(values, ddof=1)))

                offset_x = x + (gaussian_index - 1) * 0.045
                ax.plot(offset_x, means, color=colour, linewidth=1.2, zorder=2)
                ax.errorbar(
                    offset_x,
                    means,
                    yerr=standard_deviations,
                    fmt="o",
                    markersize=4,
                    color=colour,
                    capsize=2,
                    elinewidth=0.8,
                    zorder=3,
                )
                for resolution, point_x, mean in zip(RESOLUTIONS, offset_x, means):
                    if (
                        resolution,
                        camera_count,
                        budget,
                    ) in undertrained_configs:
                        ax.plot(
                            point_x,
                            mean,
                            marker="o",
                            markersize=4,
                            markerfacecolor="white",
                            markeredgecolor=colour,
                            linestyle="none",
                            zorder=4,
                        )

            if row_index == 0:
                ax.set_title(f"{camera_count} cameras per patch", fontsize=9)
            if column_index == 0:
                ax.set_ylabel(metric_label, fontsize=9)
            if row_index == len(metrics) - 1:
                ax.set_xticks(x, ("1024", "2048", "Full"))
                ax.set_xlabel("Training resolution", fontsize=8)
            ax.grid(axis="y", alpha=0.2, linewidth=0.6)
            ax.spines[["top", "right"]].set_visible(False)
            ax.tick_params(labelsize=7)

    handles = [
        Line2D(
            [],
            [],
            color=colour,
            marker="o",
            linestyle="none",
            markersize=4,
            label=label,
        )
        for colour, label in zip(colours, ("500k", "1M", "2M"))
    ] + [
        Line2D(
            [],
            [],
            color="black",
            marker="o",
            markerfacecolor="white",
            linestyle="none",
            markersize=4,
            label="<90% completion in ≥1 dataset probe",
        )
    ]
    fig.legend(
        handles=handles,
        title="Gaussian budget per patch",
        loc="lower center",
        bbox_to_anchor=(0.5, 0.005),
        ncol=4,
        frameon=False,
        fontsize=8,
        title_fontsize=8,
    )
    bottom = 0.23 if len(metrics) == 1 else 0.13
    fig.subplots_adjust(
        left=0.08,
        right=0.99,
        top=0.94 if len(metrics) == 1 else 0.96,
        bottom=bottom,
        hspace=0.18,
        wspace=0.18,
    )
    fig.savefig(output, dpi=360)
    plt.close(fig)


def main() -> None:
    """Generate and verify the final all-metric and LPIPS figures."""
    cells = load_cells()
    undertrained_configs = load_undertrained_configs()
    outputs = (
        (
            METRICS,
            OUTPUT_DIR / "stage2_3dgs_interaction_metrics.png",
            (8.2, 6.8),
        ),
        (
            (METRICS[0],),
            OUTPUT_DIR / "stage2_3dgs_interaction_lpips.png",
            (7.2, 3.8),
        ),
    )
    for metrics, output, figure_size in outputs:
        save_interactions(cells, undertrained_configs, metrics, output, figure_size)
        if output.stat().st_size == 0:
            raise RuntimeError(f"Empty output: {output}")


if __name__ == "__main__":
    main()
