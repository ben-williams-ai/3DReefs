"""Portable, dataset-specific colour profile persistence."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reefs.colour.filters import ColourParameterSet
from reefs.colour.interpolation import Keyframe
from reefs.colour.ordering import build_image_sequence
from reefs.images.ordering import ImageItem, ImageSequence


PROFILE_SCHEMA_VERSION = 1


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class ColourProfile:
    """Saved GUI edits for exactly one ordered dataset."""

    dataset_fingerprint: str
    ordered_images: list[dict[str, Any]]
    mode: str
    ordering_method: str
    keyframes: list[Keyframe]
    created_at: str
    schema_version: int = PROFILE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Return the stable public JSON representation."""
        return {
            "schema_version": self.schema_version,
            "dataset_fingerprint": self.dataset_fingerprint,
            "ordered_images": self.ordered_images,
            "mode": self.mode,
            "ordering_method": self.ordering_method,
            "keyframes": [
                {
                    "id": item.id,
                    "relative_path": item.relative_path.as_posix(),
                    "camera_group": item.camera_group,
                    "global_position": item.global_position,
                    "camera_position": item.camera_position,
                    "list_index": item.list_index,
                    "parameters": item.parameters.as_dict() if item.parameters else None,
                    "edited": item.edited,
                }
                for item in self.keyframes
                if item.edited
            ],
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ColourProfile":
        """Validate and load a profile mapping."""
        if int(data.get("schema_version", 0)) != PROFILE_SCHEMA_VERSION:
            raise ValueError(f"Unsupported colour profile schema version: {data.get('schema_version')}")
        keyframes = [
            Keyframe(
                id=str(item["id"]),
                relative_path=Path(item["relative_path"]),
                camera_group=str(item["camera_group"]),
                global_position=int(item["global_position"]),
                camera_position=int(item["camera_position"]),
                list_index=int(item["list_index"]),
                parameters=ColourParameterSet.from_mapping(item.get("parameters")),
                edited=bool(item.get("edited", True)),
            )
            for item in data.get("keyframes", [])
        ]
        if not keyframes:
            raise ValueError("Colour profile contains no edited keyframes")
        ordered_images = list(data.get("ordered_images", []))
        if not ordered_images:
            raise ValueError("Colour profile contains no dataset images")
        return cls(
            dataset_fingerprint=str(data["dataset_fingerprint"]),
            ordered_images=ordered_images,
            mode=str(data["mode"]),
            ordering_method=str(data["ordering_method"]),
            keyframes=keyframes,
            created_at=str(data["created_at"]),
        )


def dataset_identity(raw_images: Path) -> tuple[list[dict[str, Any]], str]:
    """Return the portable ordered inventory and its fingerprint."""
    sequence = build_image_sequence(raw_images)
    ordered: list[dict[str, Any]] = []
    from reefs.diagnostics.images import image_dimensions

    for item in sequence.items:
        path = raw_images / item.relative_path
        width, height = image_dimensions(path)
        ordered.append(
            {
                "relative_path": item.relative_path.as_posix(),
                "camera_group": item.camera_group,
                "width": width,
                "height": height,
                "sha256": _sha256(path),
            }
        )
    fingerprint = hashlib.sha256(
        json.dumps(ordered, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return ordered, fingerprint


def build_profile(*, raw_images: Path, mode: str, keyframes: list[Keyframe]) -> ColourProfile:
    """Build a profile and content-bound dataset identity from GUI state."""
    sequence = build_image_sequence(raw_images)
    ordered, identity = dataset_identity(raw_images)
    return ColourProfile(
        dataset_fingerprint=identity,
        ordered_images=ordered,
        mode=mode,
        ordering_method=sequence.ordering_method,
        keyframes=[item for item in keyframes if item.edited],
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def save_profile(path: Path, profile: ColourProfile) -> None:
    """Atomically save a profile without machine-specific paths."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(profile.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def load_profile(path: Path) -> ColourProfile:
    """Load a profile JSON file."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot load colour profile {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Colour profile root must be an object")
    return ColourProfile.from_dict(data)


def profile_sha256(path: Path) -> str:
    """Return the profile file digest used for output reuse."""
    return _sha256(path)


def profile_parameters(profile: ColourProfile) -> dict[Path, ColourParameterSet]:
    """Interpolate a saved profile without requiring the original files."""
    from reefs.colour.interpolation import interpolate_parameters

    items = [
        ImageItem(
            relative_path=Path(item["relative_path"]),
            camera_group=str(item["camera_group"]),
            global_index=index,
            camera_index=sum(
                1 for previous in profile.ordered_images[:index] if previous["camera_group"] == item["camera_group"]
            ),
            width=int(item["width"]),
            height=int(item["height"]),
        )
        for index, item in enumerate(profile.ordered_images)
    ]
    sequence = ImageSequence(
        source_root=Path("."),
        items=items,
        ordering_method=profile.ordering_method,
    )
    return interpolate_parameters(sequence, profile.keyframes)
