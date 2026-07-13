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
AGGREGATE_MARKERS = {
    ("sift", "global"): "o",
    ("aliked", "global"): "s",
    ("sift", "incremental"): "P",
    ("aliked", "incremental"): "X",
}
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
        "--metric",
        choices=("all", *METRIC_LABELS),
        default="all",
        help="Metric to plot; default: all three.",
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

    for mapper in MAPPERS:
        for feature in FEATURES:
            colour = colours[(feature, mapper)]
            y_values = []
            coverage = []
            for x_index, resolution in enumerate(RESOLUTIONS):
                row = summary_lookup[(resolution, feature, mapper)]
                value = row[f"macro_mean_{metric}"]
                y_values.append(float(value) if value != "" else np.nan)
                coverage.append(int(row["successful_datasets"]))
            coverage_label = (
                f"{coverage[0]}/{denominator}"
                if len(set(coverage)) == 1
                else ",".join(f"{count}/{denominator}" for count in coverage)
            )
            (line,) = ax.plot(
                x_values,
                y_values,
                color=colour,
                linestyle="-",
                marker=AGGREGATE_MARKERS[(feature, mapper)],
                markersize=8,
                linewidth=2,
                markeredgecolor="white",
                markeredgewidth=0.7,
                label=f"{mapper.title()} {feature.upper()} ({coverage_label})",
                zorder=3,
            )
            lines.append(line)

            for dataset_index, dataset_id in enumerate(dataset_ids):
                jitter = (dataset_index - (denominator - 1) / 2) * 0.035
                for x_index, resolution in enumerate(RESOLUTIONS):
                    row = dataset_lookup.get((dataset_id, resolution, feature, mapper))
                    if row is None:
                        continue
                    ax.scatter(
                        x_values[x_index] + jitter,
                        row[f"dataset_mean_{metric}"],
                        marker=markers[dataset_id],
                        s=27,
                        color=colour,
                        alpha=0.38,
                        linewidths=0,
                        zorder=2,
                    )

    finite_values = [row[f"dataset_mean_{metric}"] for row in dataset_rows]
    y_min, y_max = min(finite_values), max(finite_values)
    span = max(y_max - y_min, 0.01)
    lower, upper = y_min - 0.10 * span, y_max + 0.10 * span
    ax.set_ylim(lower, upper)

    ax.set_xticks(x_values, ("1024", "2048", "Full"))
    ax.set_xlabel("Feature-extraction resolution")
    metric_label, direction, _ = METRIC_LABELS[metric]
    ax.set_ylabel(f"Macro-average {metric_label} {direction}")
    ax.grid(axis="y", alpha=0.2, linewidth=0.7)
    ax.spines[["top", "right"]].set_visible(False)

    dataset_handles = [
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
) -> None:
    """Render LPIPS, SSIM and PSNR as one publication figure."""
    panel_metrics = ("lpips", "ssim", "psnr")
    fig, axes = plt.subplots(1, 3, figsize=(12.0, 3.9))
    legend_handles: list[Line2D] = []
    legend_columns = 0
    for panel_index, (ax, metric) in enumerate(zip(axes, panel_metrics, strict=True)):
        dataset_rows, summary = metric_data[metric]
        lines, dataset_handles = _draw_panel(ax, dataset_rows, summary, dataset_ids, metric)
        metric_label, direction, _ = METRIC_LABELS[metric]
        ax.set_title(f"({chr(97 + panel_index)}) {metric_label} {direction}", fontsize=10)
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.tick_params(labelsize=8)
        if not legend_handles:
            legend_handles, legend_columns = _legend_handles(lines, dataset_handles)

    fig.supxlabel("Feature-extraction resolution", y=0.20, fontsize=10)
    fig.supylabel("Macro-average score", x=0.02, fontsize=10)
    fig.legend(
        handles=legend_handles,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.01),
        ncol=legend_columns,
        frameon=False,
        fontsize=8,
        handletextpad=0.3,
        columnspacing=0.8,
    )
    fig.subplots_adjust(left=0.07, right=0.99, top=0.88, bottom=0.31, wspace=0.22)
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


def main() -> int:
    """Generate Stage 1 tables and figures."""
    args = _parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics = tuple(METRIC_LABELS) if args.metric == "all" else (args.metric,)

    mapping_written = False
    for metric in metrics:
        rows = _read_rows(args.input, metric)
        dataset_count, valid_dataset_cells, summary_cells = _render_metric(
            rows, metric, args.output_dir
        )
        if not mapping_written:
            dataset_ids = sorted({row["dataset_id"] for row in rows}, key=_natural_dataset_key)
            mapping = []
            for dataset_id in dataset_ids:
                source_names = {
                    row.get("dataset", "") for row in rows if row["dataset_id"] == dataset_id
                }
                mapping.append({"dataset_id": dataset_id, "dataset": next(iter(source_names))})
            _write_csv(args.output_dir / "stage1_dataset_mapping.csv", mapping)
            mapping_written = True

        complete_patches = sum(row["status"] == "COMPLETE" for row in rows)
        failed_rows = sum(row["status"] == "FAIL" for row in rows)
        print(
            f"{metric.upper()}: validated {dataset_count} datasets × 12 configurations; "
            f"{complete_patches} complete patches, {failed_rows} failure rows, "
            f"{valid_dataset_cells} dataset/configuration means, {summary_cells} aggregate cells."
        )
    if args.metric == "all":
        _render_combined(args.input, args.output_dir)
        print("Combined LPIPS/SSIM/PSNR figure validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
