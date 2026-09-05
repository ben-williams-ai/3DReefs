#!/usr/bin/env python3
"""Create the three-panel DS2 patch clean-up figure.

Run from the repository root:
    uv run --no-project --with matplotlib --with pillow python \
        scripts/figure_creation/create_cleanup_figure.py

Inputs default to scratch/{top_down,side_view,cleaned}.png. Panels A and B
are centre-cropped to squares; panel C preserves the full image with black
padding. All panels retain their aspect ratios without distortion.
Both row and column versions are generated beside each other.
The screenshots retain their original viewpoints and are not scale-matched.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.patheffects as path_effects
from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[2]
PANELS = (
    ("top_down.png", "A"),
    ("side_view.png", "B"),
    ("cleaned.png", "C"),
)
DPI = 300
PANEL_PIXELS = 900
MARGIN_PIXELS = 18
GAP_PIXELS = 24


def load_square(path: Path, *, padded: bool = False) -> Image.Image:
    """Fit a screenshot to a square using a centre crop or black padding."""
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        if padded:
            return ImageOps.pad(
                image,
                (PANEL_PIXELS, PANEL_PIXELS),
                method=Image.Resampling.LANCZOS,
                color="black",
                centering=(0.5, 0.5),
            )
        return ImageOps.fit(
            image,
            (PANEL_PIXELS, PANEL_PIXELS),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )


def create_figure(input_dir: Path, output: Path, *, vertical: bool = False) -> None:
    """Save a 300 dpi PNG with equal square panels and reference-style borders."""
    images = [
        load_square(input_dir / filename, padded=label == "C")
        for filename, label in PANELS
    ]
    width = 2 * MARGIN_PIXELS + 3 * PANEL_PIXELS + 2 * GAP_PIXELS
    height = 2 * MARGIN_PIXELS + PANEL_PIXELS
    if vertical:
        width, height = height, width
    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 9}):
        figure = plt.figure(figsize=(width / DPI, height / DPI), dpi=DPI)
        try:
            for index, (image, (_, label)) in enumerate(zip(images, PANELS)):
                left = MARGIN_PIXELS + index * (PANEL_PIXELS + GAP_PIXELS)
                bottom = MARGIN_PIXELS
                if vertical:
                    left = MARGIN_PIXELS
                    bottom += (len(PANELS) - 1 - index) * (PANEL_PIXELS + GAP_PIXELS)
                axis = figure.add_axes(
                    (left / width, bottom / height,
                     PANEL_PIXELS / width, PANEL_PIXELS / height)
                )
                axis.imshow(image)
                axis.set_xticks([])
                axis.set_yticks([])
                text = axis.text(
                    0.96, 0.94, label,
                    transform=axis.transAxes,
                    ha="right", va="top",
                    fontsize=11, fontweight="bold", color="white",
                )
                text.set_path_effects(
                    [path_effects.withStroke(linewidth=2.5, foreground="black")]
                )
                for spine in axis.spines.values():
                    spine.set_color("black")
                    spine.set_linewidth(0.7)

            figure.canvas.draw()
            for axis in figure.axes:
                bounds = axis.get_window_extent()
                if abs(bounds.width - PANEL_PIXELS) > 0.01 or abs(
                    bounds.height - PANEL_PIXELS
                ) > 0.01:
                    raise RuntimeError(f"Panel is not {PANEL_PIXELS} pixels square")
            output.parent.mkdir(parents=True, exist_ok=True)
            figure.savefig(output, dpi=DPI, facecolor="white")
        finally:
            plt.close(figure)

    with Image.open(output) as saved:
        if saved.size != (width, height):
            raise RuntimeError(f"Unexpected output dimensions: {saved.size}")


def main() -> None:
    """Parse paths and generate the clean-up comparison figure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=ROOT / "scratch")
    parser.add_argument("--output", type=Path, default=ROOT / "experiments/results/cleanup-fig.png")
    args = parser.parse_args()
    create_figure(args.input_dir, args.output)
    print(f"Clean-up figure validated: {args.output}")
    column_output = args.output.with_stem(f"{args.output.stem}-column")
    create_figure(args.input_dir, column_output, vertical=True)
    print(f"Clean-up column figure validated: {column_output}")


if __name__ == "__main__":
    main()
