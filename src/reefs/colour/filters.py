"""Wildflow-style colour filter parameter handling."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image


class ColourDevice(StrEnum):
    """Colour processing device selected for an apply run."""

    CPU = "cpu"
    CUDA = "cuda"


@dataclass(frozen=True)
class ColourParameterSet:
    """Complete set of colour restoration parameters.

    Defaults are neutral unless the Wildflow source behaviour defines otherwise.
    """

    gray_world: float = 0.0
    warmth: float = 0.0
    tint: float = 0.0
    saturation: float = 1.0
    blue_reduction: float = 0.0
    brightness: float = 0.0
    contrast: float = 0.0
    shadows: float = 0.0
    blacks: float = 0.0
    highlights: float = 0.0
    dehaze_strength: float = 0.0
    dehaze_omega: float = 0.9

    def as_dict(self) -> dict[str, float]:
        """Return JSON-serialisable parameter values."""
        return asdict(self)

    @classmethod
    def from_mapping(cls, values: dict[str, float] | None) -> "ColourParameterSet":
        """Build a parameter set from stored values, filling neutral defaults."""
        if values is None:
            return cls()
        allowed = set(cls().__dataclass_fields__)  # type: ignore[attr-defined]
        unexpected = set(values) - allowed
        if unexpected:
            raise ValueError(f"Unknown colour parameters: {', '.join(sorted(unexpected))}")
        return cls(**{key: float(value) for key, value in values.items()})


FILTER_ORDER = (
    "gray_world",
    "warmth",
    "tint",
    "saturation",
    "blue_reduction",
    "brightness_contrast",
    "shadows",
    "blacks",
    "highlights",
    "dehaze",
)


def select_colour_device(prefer_acceleration: bool = True) -> tuple[ColourDevice, str]:
    """Return the best available processing device and a human-readable note."""
    if prefer_acceleration:
        try:
            import torch

            if torch.cuda.is_available():
                return ColourDevice.CUDA, "Using CUDA acceleration for colour restoration."
        except Exception:
            pass
    return ColourDevice.CPU, "Using CPU colour restoration."


def apply_colour_filters(image: "Image.Image", parameters: ColourParameterSet) -> "Image.Image":
    """Apply colour filters in the Wildflow source order."""
    from PIL import ImageEnhance

    result = image.convert("RGB")
    if parameters.gray_world:
        result = _apply_gray_world(result, strength=parameters.gray_world)
    if parameters.warmth:
        result = _channel_shift(result, red_delta=parameters.warmth, green_delta=0.0, blue_delta=-parameters.warmth)
    if parameters.tint:
        result = _channel_shift(result, red_delta=parameters.tint, green_delta=-parameters.tint, blue_delta=0.0)
    if parameters.saturation != 1.0:
        result = ImageEnhance.Color(result).enhance(parameters.saturation)
    if parameters.blue_reduction:
        result = _channel_shift(result, red_delta=0.0, green_delta=0.0, blue_delta=-parameters.blue_reduction)
    if parameters.brightness or parameters.contrast:
        result = ImageEnhance.Brightness(result).enhance(max(0.0, 1.0 + parameters.brightness))
        result = ImageEnhance.Contrast(result).enhance(max(0.0, 1.0 + parameters.contrast))
    if parameters.shadows:
        result = ImageEnhance.Brightness(result).enhance(max(0.0, 1.0 + parameters.shadows * 0.5))
    if parameters.blacks:
        result = ImageEnhance.Contrast(result).enhance(max(0.0, 1.0 + parameters.blacks * 0.5))
    if parameters.highlights:
        result = ImageEnhance.Brightness(result).enhance(max(0.0, 1.0 + parameters.highlights * 0.25))
    if parameters.dehaze_strength:
        result = ImageEnhance.Contrast(result).enhance(max(0.0, 1.0 + parameters.dehaze_strength * parameters.dehaze_omega))
    return result


def _channel_shift(
    image: "Image.Image",
    *,
    red_delta: float,
    green_delta: float,
    blue_delta: float,
) -> "Image.Image":
    import numpy as np
    from PIL import Image

    array = np.asarray(image.convert("RGB"), dtype=np.float32)
    array[..., 0] = array[..., 0] * (1.0 + red_delta)
    array[..., 1] = array[..., 1] * (1.0 + green_delta)
    array[..., 2] = array[..., 2] * (1.0 + blue_delta)
    return Image.fromarray(np.clip(array, 0, 255).astype("uint8"), mode="RGB")


def _apply_gray_world(image: "Image.Image", *, strength: float) -> "Image.Image":
    import numpy as np
    from PIL import Image

    array = np.asarray(image.convert("RGB"), dtype=np.float32)
    means = array.reshape(-1, 3).mean(axis=0)
    target = means.mean()
    scale = np.divide(target, means, out=np.ones_like(means), where=means != 0)
    corrected = array * (1.0 + (scale - 1.0) * strength)
    return Image.fromarray(np.clip(corrected, 0, 255).astype("uint8"), mode="RGB")
