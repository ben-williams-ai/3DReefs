#!/usr/bin/env python3
"""Rework colour-enhance-fig.png without its (unavailable) source images.

The raw/corrected datasets are not on this machine, so instead of re-running
create_colour_enhancement_figure.py this script slices the existing PNG along
its panel borders and restacks the strips to:
  1. tighten the gap between the Raw/Colour-enhanced headers and the images,
  2. emit a second figure containing only datasets 4 and 5.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

RESULTS = Path(__file__).resolve().parents[2] / "experiments/results"
SOURCE = RESULTS / "colour-enhance-fig.png"
SUBSET_OUTPUT = RESULTS / "colour-enhance-fig-ds45.png"
SUBSET_DATASETS = (4, 5)

TOP_MARGIN = 14
HEADER_GAP = 15
ROW_GAP = 27
BOTTOM_MARGIN = 28


def find_rows(gray: np.ndarray) -> list[tuple[int, int]]:
    """Locate the six image rows via their long horizontal spine lines."""
    dark = (gray < 60).sum(axis=1)
    ys = np.where(dark > 1200)[0]
    bands: list[tuple[int, int]] = []
    start = prev = int(ys[0])
    for y in ys[1:]:
        if y > prev + 1:
            bands.append((start, prev))
            start = int(y)
        prev = int(y)
    bands.append((start, prev))
    if len(bands) != 12:
        raise RuntimeError(f"Expected 12 spine bands, found {len(bands)}")
    return [(bands[i][0], bands[i + 1][1]) for i in range(0, 12, 2)]


def header_strip(gray: np.ndarray, first_row_top: int) -> tuple[int, int]:
    """Vertical extent of the column-header text, with a little padding."""
    text = np.where((gray[: first_row_top - 3] < 120).sum(axis=1) > 0)[0]
    return int(text.min()) - 3, int(text.max()) + 3


def stack(source: np.ndarray, strips: list[np.ndarray], gaps: list[int]) -> Image.Image:
    height = TOP_MARGIN + sum(s.shape[0] for s in strips) + sum(gaps) + BOTTOM_MARGIN
    canvas = np.full((height, source.shape[1], source.shape[2]), 255, dtype=np.uint8)
    y = TOP_MARGIN
    for strip, gap in zip(strips, [*gaps, 0]):
        canvas[y : y + strip.shape[0]] = strip
        y += strip.shape[0] + gap
    return Image.fromarray(canvas)


def main() -> None:
    with Image.open(SOURCE) as image:
        rgb = np.asarray(image.convert("RGB"))
    gray = np.asarray(Image.fromarray(rgb).convert("L"))

    rows = find_rows(gray)
    text_top, text_bottom = header_strip(gray, rows[0][0])
    header = rgb[text_top : text_bottom + 1]
    row_strips = [rgb[top - 1 : bottom + 2] for top, bottom in rows]

    def build(indices: tuple[int, ...]) -> Image.Image:
        strips = [header, *(row_strips[i - 1] for i in indices)]
        gaps = [HEADER_GAP, *([ROW_GAP] * (len(indices) - 1))]
        return stack(rgb, strips, gaps)

    build(tuple(range(1, 7))).save(SOURCE, dpi=(300, 300))
    build(SUBSET_DATASETS).save(SUBSET_OUTPUT, dpi=(300, 300))
    print(f"Rewrote {SOURCE}")
    print(f"Wrote {SUBSET_OUTPUT}")


if __name__ == "__main__":
    main()
