#!/usr/bin/env python3
"""Plot Stage 1 SfM interactions from the patch-level results table."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
from PIL import Image


RESOLUTIONS = ("1024", "2048", "full")
FEATURES = ("sift", "aliked")
MAPPERS = ("global", "incremental")
DATASET_MARKERS = ("o", "s", "D", "^", "v", "P", "X")
METRIC_LABELS = {
    "lpips": ("LPIPS", "↓", "Lower"),
    "psnr": ("PSNR (dB)", "↑", "Higher"),
    "ssim": ("SSIM", "↑", "Higher"),
}
REQUIRED_COLUMNS = {
    "dataset_id",
    "feature_resolution",
    "feature_type",
    "mapper",
    "patch_id",
    "row_type",
    "status",
}


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=Path("experiments/results/stage1/stage1_results.csv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("experiments/results/stage1"),
    )
    parser.add_argument(
        "--improved-output",
        type=Path,
        help="Write only the improved three-panel PNG to this path.",
    )
    parser.add_argument(
        "--stddev",
        action="store_true",
        help="Replace dataset points with ±1 sample-standard-deviation error bars.",
    )
    return parser.parse_args()


def _read_rows(path: Path, metric: str) -> list[dict[str, Any]]:
    """Read and strictly validate the tidy patch-level results table."""
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = (REQUIRED_COLUMNS | {metric}) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")
        rows = list(reader)

    if not rows:
        raise ValueError(f"No rows in {path}")
    seen_patches: set[tuple[str, str, str, str, str]] = set()
    attempts: set[tuple[str, str, str, str]] = set()
    datasets: set[str] = set()
    for line_number, row in enumerate(rows, start=2):
        context = f"{path}:{line_number}"
        factor_values = (
            row["feature_resolution"].lower(),
            row["feature_type"].lower(),
            row["mapper"].lower(),
        )
        if factor_values[0] not in RESOLUTIONS:
            raise ValueError(f"{context}: invalid feature_resolution {factor_values[0]!r}")
        if factor_values[1] not in FEATURES:
            raise ValueError(f"{context}: invalid feature_type {factor_values[1]!r}")
        if factor_values[2] not in MAPPERS:
            raise ValueError(f"{context}: invalid mapper {factor_values[2]!r}")
        if row["status"] not in {"COMPLETE", "FAIL"}:
            raise ValueError(f"{context}: status must be COMPLETE or FAIL")
        if row["row_type"] not in {"patch", "run"}:
            raise ValueError(f"{context}: row_type must be patch or run")
        if row["row_type"] == "patch" and not row["patch_id"]:
            raise ValueError(f"{context}: patch row has no patch_id")

        value = row[metric].strip()
        if row["status"] == "COMPLETE":
            try:
                parsed = float(value)
            except ValueError as error:
                raise ValueError(f"{context}: COMPLETE row has invalid {metric}") from error
            if not np.isfinite(parsed):
                raise ValueError(f"{context}: COMPLETE row has non-finite {metric}")
            row[metric] = parsed
        elif value:
            raise ValueError(f"{context}: FAIL row must not contain {metric}")
        else:
            row[metric] = np.nan

        row["feature_resolution"], row["feature_type"], row["mapper"] = factor_values
        datasets.add(row["dataset_id"])
        attempt = (row["dataset_id"], *factor_values)
        attempts.add(attempt)
        if row["row_type"] == "patch":
            patch_key = (*attempt, row["patch_id"])
            if patch_key in seen_patches:
                raise ValueError(f"{context}: duplicate patch row {patch_key}")
            seen_patches.add(patch_key)

    expected = {
        (dataset, resolution, feature, mapper)
        for dataset in datasets
        for resolution in RESOLUTIONS
        for feature in FEATURES
        for mapper in MAPPERS
    }
    if attempts != expected:
        missing_attempts = sorted(expected - attempts)
        extra_attempts = sorted(attempts - expected)
        raise ValueError(
            f"Expected all 12 configurations for every dataset; "
            f"missing={missing_attempts}, extra={extra_attempts}"
        )
    return rows


def _natural_dataset_key(dataset_id: str) -> tuple[str, int]:
    """Sort identifiers such as D2 before D10."""
    prefix = dataset_id.rstrip("0123456789")
    suffix = dataset_id[len(prefix) :]
    return prefix, int(suffix) if suffix else 0


def _aggregate(
    rows: list[dict[str, Any]], metric: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """Average patches within datasets, then datasets within configurations."""
    values: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)
    for row in rows:
        if row["status"] == "COMPLETE":
            key = (
                row["dataset_id"],
                row["feature_resolution"],
                row["feature_type"],
                row["mapper"],
            )
            values[key].append(row[metric])

    dataset_rows = [
        {
            "dataset_id": key[0],
            "feature_resolution": key[1],
            "feature_type": key[2],
            "mapper": key[3],
            f"dataset_mean_{metric}": float(np.mean(patch_values)),
            "completed_patches": len(patch_values),
        }
        for key, patch_values in sorted(values.items())
    ]
    by_config: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for row in dataset_rows:
        by_config[
            (row["feature_resolution"], row["feature_type"], row["mapper"])
        ].append(row[f"dataset_mean_{metric}"])

    dataset_ids = sorted({row["dataset_id"] for row in rows}, key=_natural_dataset_key)
    summary = []
    for resolution in RESOLUTIONS:
        for feature in FEATURES:
            for mapper in MAPPERS:
                config_values = by_config[(resolution, feature, mapper)]
                summary.append(
                    {
                        "feature_resolution": resolution,
                        "feature_type": feature,
                        "mapper": mapper,
                        f"macro_mean_{metric}": (
                            float(np.mean(config_values)) if config_values else ""
                        ),
                        "successful_datasets": len(config_values),
                        "attempted_datasets": len(dataset_ids),
                    }
                )
    return dataset_rows, summary, dataset_ids


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write a non-empty list of dictionaries as CSV."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _colours() -> dict[tuple[str, str], str]:
    pairs = [(feature, mapper) for mapper in MAPPERS for feature in FEATURES]
    cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    return {pair: cycle[index] for index, pair in enumerate(pairs)}


def _draw_panel(
    ax: Any,
    dataset_rows: list[dict[str, Any]],
    summary: list[dict[str, Any]],
    dataset_ids: list[str],
    metric: str,
    show_stddev: bool = False,
) -> tuple[list[Line2D], list[Line2D]]:
    """Draw one metric panel and return shared-legend handles."""
    colours = _colours()
    markers = dict(zip(dataset_ids, DATASET_MARKERS, strict=False))
    x_values = np.arange(len(RESOLUTIONS), dtype=float)
    lines: list[Line2D] = []
    summary_lookup = {
        (row["feature_resolution"], row["feature_type"], row["mapper"]): row
        for row in summary
    }
    dataset_lookup = {
        (
            row["dataset_id"],
            row["feature_resolution"],
            row["feature_type"],
            row["mapper"],
        ): row
        for row in dataset_rows
    }
    denominator = len(dataset_ids)

    for feature in FEATURES:
        colour = colours[(feature, "global")]
        aggregate_x = x_values + (
            (-0.045 if feature == "sift" else 0.045) if show_stddev else 0.0
        )
        y_values = [
            float(summary_lookup[(resolution, feature, "global")][f"macro_mean_{metric}"])
            for resolution in RESOLUTIONS
        ]
        (line,) = ax.plot(
            aggregate_x,
            y_values,
            color=colour,
            linestyle="none" if show_stddev else ":",
            marker="o",
            markersize=5 if show_stddev else 6,
            linewidth=2,
            markerfacecolor=colour if show_stddev else "none",
            markeredgecolor=colour,
            markeredgewidth=1.2,
            label=f"Global {feature.upper()}",
            zorder=3,
        )
        lines.append(line)

        if show_stddev:
            standard_deviations = [
                np.std(
                    [
                        dataset_lookup[(dataset_id, resolution, feature, "global")][
                            f"dataset_mean_{metric}"
                        ]
                        for dataset_id in dataset_ids
                    ],
                    ddof=1,
                )
                for resolution in RESOLUTIONS
            ]
            ax.errorbar(
                aggregate_x,
                y_values,
                yerr=standard_deviations,
                fmt="none",
                ecolor=colour,
                elinewidth=1.2,
                capsize=3,
                alpha=0.7,
                zorder=2,
            )
        else:
            for dataset_index, dataset_id in enumerate(dataset_ids):
                column_offset = (dataset_index - (denominator - 1) / 2) * 0.09
                for x_index, resolution in enumerate(RESOLUTIONS):
                    row = dataset_lookup[(dataset_id, resolution, feature, "global")]
                    ax.scatter(
                        x_values[x_index] + column_offset,
                        row[f"dataset_mean_{metric}"],
                        marker=markers[dataset_id],
                        s=25,
                        facecolor=colour,
                        edgecolor=colour,
                        alpha=0.40,
                        linewidths=0.45,
                        zorder=2,
                    )

    incremental_values = [
        dataset_lookup[("D3", resolution, "sift", "incremental")][f"dataset_mean_{metric}"]
        for resolution in RESOLUTIONS
    ]
    (incremental_handle,) = ax.plot(
        x_values,
        incremental_values,
        linestyle="none",
        color=colours[("sift", "incremental")],
        linewidth=1.5,
        marker="o",
        markersize=5 if show_stddev else 6,
        markerfacecolor="none",
        markeredgecolor=colours[("sift", "incremental")],
        markeredgewidth=1.2,
        label="Incremental SIFT",
        zorder=4,
    )
    lines.append(incremental_handle)

    plotted_rows = [
        row
        for row in dataset_rows
        if row["mapper"] == "global"
        or (row["mapper"] == "incremental" and row["feature_type"] == "sift" and row["dataset_id"] == "D3")
    ]
    finite_values = [row[f"dataset_mean_{metric}"] for row in plotted_rows]
    y_min, y_max = min(finite_values), max(finite_values)
    span = max(y_max - y_min, 0.01)
    lower, upper = y_min - 0.10 * span, y_max + 0.10 * span
    ax.set_ylim(lower, upper)

    ax.set_xticks(x_values, ("1024", "2048", "Full"))
    ax.set_xlabel("Feature-extraction resolution")
    metric_label, direction, _ = METRIC_LABELS[metric]
    ax.set_ylabel(f"{metric_label} {direction}")
    ax.grid(axis="y", alpha=0.2, linewidth=0.7)
    ax.spines[["top", "right"]].set_visible(False)

    dataset_handles = [] if show_stddev else [
        Line2D(
            [],
            [],
            marker=markers[dataset_id],
            linestyle="none",
            color="0.35",
            markersize=5.5,
            label=dataset_id,
        )
        for dataset_id in dataset_ids
    ]
    return lines, dataset_handles


def _legend_handles(
    lines: list[Line2D], dataset_handles: list[Line2D]
) -> tuple[list[Line2D], int]:
    """Arrange methods above ordered dataset markers in one legend."""
    legend_columns = max(len(dataset_handles), len(lines))
    method_row = [
        *lines,
        *(Line2D([], [], linestyle="none", label="") for _ in range(legend_columns - len(lines))),
    ]
    dataset_row = [
        *dataset_handles,
        *(
            Line2D([], [], linestyle="none", label="")
            for _ in range(legend_columns - len(dataset_handles))
        ),
    ]
    legend_handles = [handle for pair in zip(method_row, dataset_row) for handle in pair]
    return legend_handles, legend_columns


def _plot(
    dataset_rows: list[dict[str, Any]],
    summary: list[dict[str, Any]],
    dataset_ids: list[str],
    metric: str,
    output: Path,
    *,
    diagnostic: bool,
) -> None:
    """Render the publication or diagnostic single-metric plot."""
    figure_size = (10.5, 6.2) if diagnostic else (7.1, 4.5)
    fig, ax = plt.subplots(figsize=figure_size)
    lines, dataset_handles = _draw_panel(ax, dataset_rows, summary, dataset_ids, metric)
    if diagnostic:
        ax.set_title("Stage 1 SfM ablation interaction (diagnostic)")
    legend_handles, legend_columns = _legend_handles(lines, dataset_handles)
    ax.legend(
        handles=legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.17),
        ncol=legend_columns,
        frameon=False,
        fontsize=7,
        handletextpad=0.3,
        columnspacing=0.6,
    )
    fig.subplots_adjust(
        top=0.88 if diagnostic else 0.96,
        bottom=0.27,
        left=0.10 if diagnostic else 0.12,
        right=0.98,
    )
    fig.savefig(output, dpi=360)
    plt.close(fig)


def _plot_combined(
    metric_data: dict[str, tuple[list[dict[str, Any]], list[dict[str, Any]]]],
    dataset_ids: list[str],
    output: Path,
    show_stddev: bool = False,
) -> None:
    """Render LPIPS, SSIM and PSNR as one publication figure."""
    panel_metrics = ("lpips", "ssim", "psnr")
    fig, axes = plt.subplots(1, 3, figsize=((7.2, 3.8) if show_stddev else (12.0, 3.8)))
    method_handles: list[Line2D] = []
    shared_dataset_handles: list[Line2D] = []
    for panel_index, (ax, metric) in enumerate(zip(axes, panel_metrics, strict=True)):
        dataset_rows, summary = metric_data[metric]
        lines, dataset_handles = _draw_panel(
            ax, dataset_rows, summary, dataset_ids, metric, show_stddev
        )
        metric_label, direction, _ = METRIC_LABELS[metric]
        if not show_stddev:
            ax.set_title(f"({chr(97 + panel_index)}) {metric_label} {direction}", fontsize=10)
        ax.set_xlabel("Feature-extraction resolution", fontsize=9)
        ax.tick_params(labelsize=8)
        if not method_handles:
            method_handles = lines
            shared_dataset_handles = dataset_handles

    fig.legend(
        handles=method_handles,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.04 if show_stddev else 0.095),
        ncol=len(method_handles),
        frameon=False,
        fontsize=8,
        handletextpad=0.4,
        columnspacing=1.2,
    )
    if shared_dataset_handles:
        fig.legend(
            handles=shared_dataset_handles,
            loc="lower center",
            bbox_to_anchor=(0.5, 0.015),
            ncol=len(shared_dataset_handles),
            frameon=False,
            fontsize=8,
            handletextpad=0.3,
            columnspacing=1.4,
        )
    fig.subplots_adjust(
        left=0.085 if show_stddev else 0.065,
        right=0.99,
        top=0.97 if show_stddev else 0.88,
        bottom=0.25 if show_stddev else 0.32,
        wspace=0.42 if show_stddev else 0.25,
    )
    fig.savefig(output, dpi=360)
    plt.close(fig)


def _output_stem(metric: str) -> str:
    """Keep the original LPIPS filenames and suffix the additional metrics."""
    return "stage1_sfm_interaction" + ("" if metric == "lpips" else f"_{metric}")


def _verify_outputs(output_dir: Path, summary: list[dict[str, Any]], metric: str) -> None:
    """Check expected files, image dimensions, and all 12 summary cells."""
    stem = _output_stem(metric)
    expected_files = [output_dir / f"{stem}.{suffix}" for suffix in ("pdf", "png")]
    expected_files.extend(
        [
            output_dir / f"{stem}_diagnostic.png",
            output_dir / f"{stem}_summary.csv",
            output_dir / f"{stem}_caption.txt",
        ]
    )
    missing = [str(path) for path in expected_files if not path.is_file() or not path.stat().st_size]
    if missing:
        raise RuntimeError(f"Missing or empty outputs: {missing}")
    if len(summary) != 12:
        raise RuntimeError(f"Expected 12 aggregate cells, found {len(summary)}")
    with Image.open(output_dir / f"{stem}.png") as image:
        if image.width < 2000 or image.height < 1000:
            raise RuntimeError(f"Publication PNG is unexpectedly small: {image.size}")
    for row in summary:
        value = row[f"macro_mean_{metric}"]
        if row["successful_datasets"] and value == "":
            raise RuntimeError(f"Missing aggregate mean for {row}")


def _render_metric(
    rows: list[dict[str, Any]], metric: str, output_dir: Path
) -> tuple[int, int, int]:
    """Aggregate, render and verify one metric."""
    dataset_rows, summary, dataset_ids = _aggregate(rows, metric)
    stem = _output_stem(metric)
    _write_csv(output_dir / f"{stem}_summary.csv", summary)
    metric_label, _, quality_direction = METRIC_LABELS[metric]
    caption = (
        f"Stage 1 SfM ablations across {len(dataset_ids)} underwater datasets. Large markers and "
        f"connected lines show macro-average {metric_label} across datasets with valid downstream "
        "evaluations, while faint markers show dataset-level patch means. Legend fractions report "
        f"datasets with valid results out of {len(dataset_ids)}. Missing markers indicate failed, "
        f"excluded, or incomplete evaluations. {quality_direction} {metric_label} is better."
    )
    (output_dir / f"{stem}_caption.txt").write_text(caption + "\n", encoding="utf-8")

    _plot(
        dataset_rows,
        summary,
        dataset_ids,
        metric,
        output_dir / f"{stem}.png",
        diagnostic=False,
    )
    _plot(
        dataset_rows,
        summary,
        dataset_ids,
        metric,
        output_dir / f"{stem}.pdf",
        diagnostic=False,
    )
    _plot(
        dataset_rows,
        summary,
        dataset_ids,
        metric,
        output_dir / f"{stem}_diagnostic.png",
        diagnostic=True,
    )
    _verify_outputs(output_dir, summary, metric)
    return len(dataset_ids), len(dataset_rows), len(summary)


def _render_combined(input_path: Path, output_dir: Path) -> None:
    """Generate and verify the shared-legend three-metric figure."""
    metric_data: dict[str, tuple[list[dict[str, Any]], list[dict[str, Any]]]] = {}
    dataset_ids: list[str] | None = None
    combined_summary: list[dict[str, Any]] = []
    for metric in ("lpips", "ssim", "psnr"):
        rows = _read_rows(input_path, metric)
        dataset_rows, summary, current_dataset_ids = _aggregate(rows, metric)
        if dataset_ids is not None and current_dataset_ids != dataset_ids:
            raise ValueError(f"Dataset IDs differ for {metric}: {current_dataset_ids}")
        dataset_ids = current_dataset_ids
        metric_data[metric] = (dataset_rows, summary)
        for row in summary:
            combined_summary.append(
                {
                    "metric": metric,
                    "feature_resolution": row["feature_resolution"],
                    "feature_type": row["feature_type"],
                    "mapper": row["mapper"],
                    "macro_mean": row[f"macro_mean_{metric}"],
                    "successful_datasets": row["successful_datasets"],
                    "attempted_datasets": row["attempted_datasets"],
                }
            )

    assert dataset_ids is not None
    stem = "stage1_sfm_interaction_metrics"
    _plot_combined(metric_data, dataset_ids, output_dir / f"{stem}.png")
    _plot_combined(metric_data, dataset_ids, output_dir / f"{stem}.pdf")
    _write_csv(output_dir / f"{stem}_summary.csv", combined_summary)
    caption = (
        f"Stage 1 SfM ablations across {len(dataset_ids)} underwater datasets: (a) LPIPS, "
        "(b) SSIM and (c) PSNR. Large markers and connected lines show macro-averages across "
        "datasets with valid downstream evaluations; faint markers show dataset-level patch "
        "means. Legend fractions report valid datasets out of the total. Missing markers indicate "
        "failed, excluded or incomplete evaluations. Lower LPIPS and higher SSIM/PSNR are better."
    )
    (output_dir / f"{stem}_caption.txt").write_text(caption + "\n", encoding="utf-8")

    expected = [
        output_dir / f"{stem}.png",
        output_dir / f"{stem}.pdf",
        output_dir / f"{stem}_summary.csv",
        output_dir / f"{stem}_caption.txt",
    ]
    missing = [str(path) for path in expected if not path.is_file() or not path.stat().st_size]
    if missing:
        raise RuntimeError(f"Missing or empty combined outputs: {missing}")
    with Image.open(output_dir / f"{stem}.png") as image:
        if image.width < 4000 or image.height < 1200:
            raise RuntimeError(f"Combined PNG is unexpectedly small: {image.size}")


def _render_improved_only(
    input_path: Path, output_path: Path, show_stddev: bool = False
) -> None:
    """Validate the requested scientific subset and write one improved PNG."""
    if output_path.suffix.lower() != ".png":
        raise ValueError(f"Improved output must be a PNG: {output_path}")

    metric_data: dict[str, tuple[list[dict[str, Any]], list[dict[str, Any]]]] = {}
    expected_datasets: list[str] | None = None
    for metric in ("lpips", "ssim", "psnr"):
        rows = _read_rows(input_path, metric)
        dataset_rows, summary, dataset_ids = _aggregate(rows, metric)
        if expected_datasets is not None and dataset_ids != expected_datasets:
            raise ValueError(f"Dataset IDs differ for {metric}: {dataset_ids}")
        expected_datasets = dataset_ids

        summary_lookup = {
            (row["feature_resolution"], row["feature_type"], row["mapper"]): row
            for row in summary
        }
        for resolution in RESOLUTIONS:
            for feature in FEATURES:
                values = [
                    row[f"dataset_mean_{metric}"]
                    for row in dataset_rows
                    if row["feature_resolution"] == resolution
                    and row["feature_type"] == feature
                    and row["mapper"] == "global"
                ]
                aggregate = summary_lookup[(resolution, feature, "global")]
                if len(values) != len(dataset_ids) or aggregate["successful_datasets"] != len(
                    dataset_ids
                ):
                    raise ValueError(f"{metric}/{resolution}/{feature}: incomplete global coverage")
                if not np.isclose(
                    aggregate[f"macro_mean_{metric}"], np.mean(values), rtol=0.0, atol=1e-12
                ):
                    raise ValueError(f"{metric}/{resolution}/{feature}: incorrect macro-average")

            incremental_ids = {
                row["dataset_id"]
                for row in dataset_rows
                if row["feature_resolution"] == resolution
                and row["feature_type"] == "sift"
                and row["mapper"] == "incremental"
            }
            if incremental_ids != {"D3"}:
                raise ValueError(
                    f"{metric}/{resolution}/incremental SIFT must contain only D3: "
                    f"{sorted(incremental_ids)}"
                )
            if any(
                row["feature_resolution"] == resolution
                and row["feature_type"] == "aliked"
                and row["mapper"] == "incremental"
                for row in dataset_rows
            ):
                raise ValueError(f"{metric}/{resolution}: unexpected Incremental ALIKED values")
        metric_data[metric] = (dataset_rows, summary)

    assert expected_datasets is not None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _plot_combined(metric_data, expected_datasets, output_path, show_stddev)
    with Image.open(output_path) as image:
        minimum_width = 2500 if show_stddev else 4000
        if image.width < minimum_width or image.height < 1200:
            raise RuntimeError(f"Improved PNG is unexpectedly small: {image.size}")


def main() -> int:
    """Generate Stage 1 tables and figures."""
    args = _parse_args()
    if args.improved_output is not None:
        _render_improved_only(args.input, args.improved_output, args.stddev)
        print(f"Improved figure validated: {args.improved_output}")
        return 0

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / "stage1_sfm_interaction_metrics.png"
    _render_improved_only(args.input, output, show_stddev=True)
    print(f"Stage 1 figure validated: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
