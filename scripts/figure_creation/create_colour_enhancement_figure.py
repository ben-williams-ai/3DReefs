#!/usr/bin/env python3
"""Create the supplementary raw-versus-colour-enhanced image figure."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "experiments/results/colour-enhance-fig.png"
SELECTED_IMAGES = (
    ("dataset1", "07_cam2_GP_Right (1316).JPG"),
    ("dataset2", "01_cam1_GPAA0812.JPG"),
    ("dataset3", "07_cam2_DSC07346.jpg"),
    ("dataset4", "07_cam2_GP2 (3238).JPG"),
    (
        "dataset5",
        "07_cam2_001558_right_cam2_vid1_DJI_20251002143952_0027_D_"
        "frame001558_t000389250ms.jpg",
    ),
    ("dataset6", "08_cam2_002993_cam2_stopnitzky.jpg"),
)
TARGET_SIZE = (1200, 620)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_root", type=Path, help="Directory containing datasetN/raw and corrected")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def load_pair(input_root: Path, dataset: str, filename: str) -> tuple[Image.Image, Image.Image]:
    """Load and identically centre-crop one raw/corrected image pair."""
    images = []
    for variant in ("raw", "corrected"):
        path = input_root / dataset / variant / filename
        if not path.is_file():
            raise FileNotFoundError(path)
        with Image.open(path) as source:
            images.append(
                ImageOps.fit(
                    ImageOps.exif_transpose(source).convert("RGB"),
                    TARGET_SIZE,
                    method=Image.Resampling.LANCZOS,
                    centering=(0.5, 0.5),
                )
            )
    return images[0], images[1]


def create_figure(input_root: Path, output: Path) -> None:
    """Render the six-dataset comparison as a publication-ready PNG."""
    figure = plt.figure(figsize=(5.76, 9.2), facecolor="white")
    grid = figure.add_gridspec(
        7,
        3,
        width_ratios=(0.075, 1, 1),
        height_ratios=(0.22, 1, 1, 1, 1, 1, 1),
        left=0.035,
        right=0.995,
        bottom=0.01,
        top=0.995,
        wspace=0.018,
        hspace=0.025,
    )

    for column, heading in enumerate(("Raw", "Colour enhanced"), start=1):
        axis = figure.add_subplot(grid[0, column])
        axis.text(0.5, 0.08, heading, ha="center", va="bottom", fontsize=9)
        axis.axis("off")

    for row, (dataset, filename) in enumerate(SELECTED_IMAGES, start=1):
        label_axis = figure.add_subplot(grid[row, 0])
        label_axis.text(
            0.5,
            0.5,
            f"Dataset {row}",
            ha="center",
            va="center",
            rotation=90,
            fontsize=8,
        )
        label_axis.axis("off")

        for column, image in enumerate(load_pair(input_root, dataset, filename), start=1):
            axis = figure.add_subplot(grid[row, column])
            axis.imshow(image)
            axis.set_xticks([])
            axis.set_yticks([])
            for spine in axis.spines.values():
                spine.set_color("black")
                spine.set_linewidth(0.7)

    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=300, facecolor="white")
    plt.close(figure)

    with Image.open(output) as image:
        if image.size != (1728, 2760):
            raise RuntimeError(f"Unexpected output dimensions: {image.size}")


def main() -> None:
    """Create and validate the supplementary figure."""
    args = parse_args()
    create_figure(args.input_root, args.output)
    print(f"Colour-enhancement figure validated: {args.output}")


if __name__ == "__main__":
    main()
