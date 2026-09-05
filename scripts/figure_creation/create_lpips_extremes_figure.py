#!/usr/bin/env python3
"""Create the supplementary highest/lowest-LPIPS held-out image figure."""

from __future__ import annotations

import re
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patheffects as path_effects
from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[2]
IMAGE_PAIRS_DIR = ROOT / "experiments/results/image-pairs"
OUTPUT = ROOT / "experiments/results/lpips-extremes-fig.png"
DATASETS = range(1, 7)
GROUPS = (("worst", "Highest LPIPS image pair"), ("best", "Lowest LPIPS image pair"))
TARGET_SIZE = (900, 620)
NAME_PATTERN = re.compile(r"^ds(\d)_(best|worst)_lpips-([\d.]+)_")


def find_comparison(dataset: int, kind: str) -> tuple[Path, float]:
    """Locate the tracked comparison JPEG for one dataset/kind and its score."""
    matches = list(IMAGE_PAIRS_DIR.glob(f"ds{dataset}_{kind}_lpips-*_comparison.jpg"))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {kind} match for dataset {dataset}, found {len(matches)}")
    path = matches[0]
    match = NAME_PATTERN.match(path.name)
    if not match:
        raise ValueError(f"unexpected filename format: {path.name}")
    return path, float(match.group(3))


def load_halves(path: Path) -> tuple[Image.Image, Image.Image]:
    """Split a ground-truth/render comparison JPEG into its two fitted halves."""
    with Image.open(path) as source:
        rgb = source.convert("RGB")
        midpoint = rgb.width // 2
        raw = rgb.crop((0, 0, midpoint, rgb.height))
        render = rgb.crop((midpoint, 0, rgb.width, rgb.height))
    fit = lambda image: ImageOps.fit(
        image, TARGET_SIZE, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5)
    )
    return fit(raw), fit(render)


def draw_score(axis: plt.Axes, score: float) -> None:
    """Overlay a white, black-outlined LPIPS score in the top-right corner."""
    text = axis.text(
        0.96,
        0.94,
        f"{score:.3f}",
        transform=axis.transAxes,
        ha="right",
        va="top",
        fontsize=11,
        fontweight="bold",
        color="white",
    )
    text.set_path_effects(
        [path_effects.withStroke(linewidth=2.5, foreground="black")]
    )


def create_figure(output: Path) -> None:
    """Render the six-dataset highest/lowest-LPIPS comparison as a PNG."""
    figure = plt.figure(figsize=(11.5, 12.9), facecolor="white")
    grid = figure.add_gridspec(
        8,
        5,
        width_ratios=(0.09, 1, 1, 1, 1),
        height_ratios=(0.24, 0.15, 1, 1, 1, 1, 1, 1),
        left=0.03,
        right=0.995,
        bottom=0.005,
        top=0.97,
        wspace=0.02,
        hspace=0.03,
    )

    for group_index, (_, heading) in enumerate(GROUPS):
        axis = figure.add_subplot(grid[0, 1 + group_index * 2 : 3 + group_index * 2])
        axis.text(0.5, 0.15, heading, ha="center", va="bottom", fontsize=17)
        axis.axis("off")

    for column in range(1, 5):
        axis = figure.add_subplot(grid[1, column])
        axis.text(0.5, 0.1, "Raw" if column % 2 == 1 else "Render", ha="center", va="bottom", fontsize=13)
        axis.axis("off")

    for row, dataset in enumerate(DATASETS, start=2):
        label_axis = figure.add_subplot(grid[row, 0])
        label_axis.text(0.5, 0.5, f"Dataset {dataset}", ha="center", va="center", rotation=90, fontsize=13)
        label_axis.axis("off")

        column = 1
        for kind, _ in GROUPS:
            path, score = find_comparison(dataset, kind)
            raw, render = load_halves(path)
            for image, is_render in ((raw, False), (render, True)):
                axis = figure.add_subplot(grid[row, column])
                axis.imshow(image)
                axis.set_xticks([])
                axis.set_yticks([])
                for spine in axis.spines.values():
                    spine.set_color("black")
                    spine.set_linewidth(0.8)
                if is_render:
                    draw_score(axis, score)
                column += 1

    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=300, facecolor="white")
    plt.close(figure)


def main() -> None:
    """Create the supplementary figure."""
    create_figure(OUTPUT)
    print(f"LPIPS-extremes figure written: {OUTPUT}")


if __name__ == "__main__":
    main()
