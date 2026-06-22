"""Persistent colour restoration state."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

from reefs.colour.filters import ColourParameterSet
from reefs.colour.interpolation import Keyframe


class ColourStatus(StrEnum):
    """Colour restoration lifecycle states."""

    INCOMPLETE = "incomplete"
    ACTIVE = "active"
    APPLYING = "applying"
    COMPLETE = "complete"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    FAILED = "failed"


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ColourRestorationState:
    """Persistent state for one run's colour restoration workflow."""

    run_id: str
    source_raw_root: Path
    output_recoloured_root: Path
    schema_version: int = 1
    status: ColourStatus = ColourStatus.INCOMPLETE
    active_session: bool = False
    mode: str = "global"
    keyframe_count: int = 10
    ordering_method: str = "natural_path"
    ordering_warnings: list[str] = field(default_factory=list)
    keyframes: list[Keyframe] = field(default_factory=list)
    interpolation: dict[str, Any] = field(default_factory=dict)
    relevant_config: dict[str, Any] = field(default_factory=dict)
    undistortion_source_sparse: Path | None = None
    final_undistorted_images: Path | None = None
    final_undistorted_sparse: Path | None = None
    current_keyframe_id: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    error: dict[str, Any] | None = None

    def with_status(self, status: ColourStatus, *, active_session: bool | None = None) -> "ColourRestorationState":
        """Return a copy with updated status/session metadata."""
        return replace(
            self,
            status=status,
            active_session=self.active_session if active_session is None else active_session,
            updated_at=utc_now(),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation."""
        data = asdict(self)
        data["status"] = self.status.value
        for key in (
            "source_raw_root",
            "output_recoloured_root",
            "undistortion_source_sparse",
            "final_undistorted_images",
            "final_undistorted_sparse",
        ):
            if data[key] is not None:
                data[key] = str(data[key])
        for keyframe in data["keyframes"]:
            keyframe["relative_path"] = str(keyframe["relative_path"])
            if keyframe["thumbnail_path"] is not None:
                keyframe["thumbnail_path"] = str(keyframe["thumbnail_path"])
            if isinstance(keyframe["parameters"], ColourParameterSet):
                keyframe["parameters"] = keyframe["parameters"].as_dict()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ColourRestorationState":
        """Build state from JSON data."""
        keyframes = []
        for item in data.get("keyframes", []):
            params = item.get("parameters")
            keyframes.append(
                Keyframe(
                    id=item["id"],
                    relative_path=Path(item["relative_path"]),
                    camera_group=item["camera_group"],
                    global_position=int(item["global_position"]),
                    camera_position=int(item["camera_position"]),
                    list_index=int(item["list_index"]),
                    parameters=ColourParameterSet.from_mapping(params) if params else None,
                    edited=bool(item["edited"]),
                    thumbnail_path=Path(item["thumbnail_path"]) if item.get("thumbnail_path") else None,
                )
            )
        return cls(
            schema_version=int(data.get("schema_version", 1)),
            run_id=str(data["run_id"]),
            status=ColourStatus(data.get("status", ColourStatus.INCOMPLETE.value)),
            active_session=bool(data.get("active_session", False)),
            mode=str(data.get("mode", "global")),
            keyframe_count=int(data.get("keyframe_count", 10)),
            ordering_method=str(data.get("ordering_method", "natural_path")),
            ordering_warnings=list(data.get("ordering_warnings", [])),
            source_raw_root=Path(data["source_raw_root"]),
            output_recoloured_root=Path(data["output_recoloured_root"]),
            keyframes=keyframes,
            interpolation=dict(data.get("interpolation", {})),
            relevant_config=dict(data.get("relevant_config", {})),
            undistortion_source_sparse=Path(data["undistortion_source_sparse"]) if data.get("undistortion_source_sparse") else None,
            final_undistorted_images=Path(data["final_undistorted_images"]) if data.get("final_undistorted_images") else None,
            final_undistorted_sparse=Path(data["final_undistorted_sparse"]) if data.get("final_undistorted_sparse") else None,
            current_keyframe_id=data.get("current_keyframe_id"),
            created_at=str(data.get("created_at", utc_now())),
            updated_at=str(data.get("updated_at", utc_now())),
            error=data.get("error"),
        )


def save_state(path: Path, state: ColourRestorationState) -> None:
    """Atomically write colour state JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def load_state(path: Path) -> ColourRestorationState:
    """Load colour state JSON."""
    return ColourRestorationState.from_dict(json.loads(path.read_text(encoding="utf-8")))


def maybe_load_state(path: Path) -> ColourRestorationState | None:
    """Load colour state when it exists."""
    if not path.exists():
        return None
    return load_state(path)


def state_allows_splat(state: ColourRestorationState | None) -> bool:
    """Return whether downstream splatting may proceed."""
    if state is None:
        return True
    if state.active_session:
        return False
    return state.status in {ColourStatus.COMPLETE, ColourStatus.SKIPPED}
