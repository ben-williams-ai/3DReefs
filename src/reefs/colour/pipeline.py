"""Colour restoration orchestration and output validation."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Callable

from reefs.colour.filters import ColourParameterSet, apply_colour_filters
from reefs.colour.interpolation import interpolate_parameters
from reefs.colour.ordering import build_image_sequence
from reefs.colour.state import ColourRestorationState, ColourStatus, load_state, save_state


class ExistingOutputDecision(StrEnum):
    """User intent for pre-existing corrected images."""

    RESUME = "resume"
    OVERWRITE = "overwrite"
    SKIP = "skip"
    FAIL = "fail"


@dataclass(frozen=True)
class CorrectedImageTreeStatus:
    """Validation status for a corrected image tree."""

    complete: bool
    missing: list[Path]
    extra: list[Path]
    dimension_mismatches: list[str]
    mode_mismatches: list[str]


EXISTING_RECOLOURED_IMAGES_MESSAGE = (
    "Found existing complete recoloured_images/ for this dataset; using it for this run."
)


def colour_state_path(run_dir: Path) -> Path:
    """Return the colour restoration state path for a run directory."""
    return run_dir / "colour_restoration" / "state.json"


def initialise_state(
    *,
    run_id: str,
    run_dir: Path,
    raw_images: Path,
    recoloured_images: Path,
) -> ColourRestorationState:
    """Create an initial colour restoration state for a run."""
    sequence = build_image_sequence(raw_images)
    return ColourRestorationState(
        run_id=run_id,
        source_raw_root=raw_images,
        output_recoloured_root=recoloured_images,
        ordering_method=sequence.ordering_method,
        ordering_warnings=sequence.ordering_warnings,
        relevant_config={"state_path": str(colour_state_path(run_dir))},
    )


def load_or_initialise_state(
    *,
    run_id: str,
    run_dir: Path,
    raw_images: Path,
    recoloured_images: Path,
) -> ColourRestorationState:
    """Load existing colour state or initialise a new one."""
    path = colour_state_path(run_dir)
    if path.exists():
        return load_state(path)
    state = initialise_state(
        run_id=run_id,
        run_dir=run_dir,
        raw_images=raw_images,
        recoloured_images=recoloured_images,
    )
    save_state(path, state)
    return state


def corrected_tree_status(*, raw_images: Path, recoloured_images: Path) -> CorrectedImageTreeStatus:
    """Check whether corrected outputs mirror raw image relative paths."""
    sequence = build_image_sequence(raw_images)
    expected = set(sequence.relative_paths)
    actual: set[Path] = set()
    if recoloured_images.exists():
        for path in recoloured_images.rglob("*"):
            if path.is_file():
                actual.add(path.relative_to(recoloured_images))
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    dimension_mismatches: list[str] = []
    mode_mismatches: list[str] = []
    for relative_path in sorted(expected & actual):
        raw_info = _image_info(raw_images / relative_path)
        recoloured_info = _image_info(recoloured_images / relative_path)
        if raw_info is None or recoloured_info is None:
            continue
        raw_size, _ = raw_info
        recoloured_size, recoloured_mode = recoloured_info
        if raw_size != recoloured_size:
            dimension_mismatches.append(f"{relative_path}: raw {raw_size}, recoloured {recoloured_size}")
        if recoloured_mode != "RGB":
            mode_mismatches.append(f"{relative_path}: recoloured mode {recoloured_mode}")
    return CorrectedImageTreeStatus(
        complete=not missing and not extra and not dimension_mismatches and not mode_mismatches,
        missing=missing,
        extra=extra,
        dimension_mismatches=dimension_mismatches,
        mode_mismatches=mode_mismatches,
    )


def _image_info(path: Path) -> tuple[tuple[int, int], str] | None:
    """Return image size and mode when Pillow can read the file."""
    try:
        from PIL import Image

        with Image.open(path) as image:
            return image.size, image.mode
    except Exception:
        return None


def require_preflight_output_decision(
    *,
    raw_images: Path,
    recoloured_images: Path,
    decision: ExistingOutputDecision | None,
) -> CorrectedImageTreeStatus:
    """Require explicit intent before using or replacing existing corrected outputs."""
    status = corrected_tree_status(raw_images=raw_images, recoloured_images=recoloured_images)
    has_outputs = recoloured_images.exists() and any(recoloured_images.rglob("*"))
    if has_outputs and decision is None:
        raise ValueError(
            "recoloured_images already contains outputs; choose resume, overwrite, skip, or fail before starting colour restoration"
        )
    if has_outputs and decision == ExistingOutputDecision.FAIL:
        raise ValueError("recoloured_images already contains outputs")
    return status


def adopt_existing_recoloured_images(
    *,
    state: ColourRestorationState,
    run_dir: Path,
) -> ColourRestorationState | None:
    """Persist a complete run state when a corrected image tree is already valid."""
    status = corrected_tree_status(
        raw_images=state.source_raw_root,
        recoloured_images=state.output_recoloured_root,
    )
    if not status.complete:
        return None
    adopted = _state_with_existing_recoloured_images(state=state, status=status)
    save_state(colour_state_path(run_dir), adopted)
    return adopted


def _state_with_existing_recoloured_images(
    *,
    state: ColourRestorationState,
    status: CorrectedImageTreeStatus,
) -> ColourRestorationState:
    """Return a completed state that records adoption of existing corrected images."""
    completed = state.with_status(ColourStatus.COMPLETE, active_session=False).to_dict()
    completed["relevant_config"] = {
        **state.relevant_config,
        "adopted_existing_recoloured_images": True,
    }
    completed["interpolation"] = {
        **state.interpolation,
        "adopted_existing_recoloured_images": True,
        "output_validation": {
            "missing": [path.as_posix() for path in status.missing],
            "extra": [path.as_posix() for path in status.extra],
            "dimension_mismatches": status.dimension_mismatches,
            "mode_mismatches": status.mode_mismatches,
        },
    }
    completed["error"] = None
    return ColourRestorationState.from_dict(completed)


def correct_image_file(*, source: Path, destination: Path, parameters: ColourParameterSet) -> None:
    """Write one corrected RGB image while preserving dimensions and extension."""
    from PIL import Image

    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        corrected = apply_colour_filters(image, parameters)
        save_kwargs: dict[str, object] = {}
        if destination.suffix.lower() in {".jpg", ".jpeg"}:
            save_kwargs.update({"quality": 95, "subsampling": 0})
        corrected.save(destination, **save_kwargs)


def apply_corrections(
    *,
    raw_images: Path,
    recoloured_images: Path,
    parameters_by_path: dict[Path, ColourParameterSet],
    progress: Callable[[int, int, Path], None] | None = None,
) -> CorrectedImageTreeStatus:
    """Apply full-resolution colour corrections to a mirrored output tree."""
    sequence = build_image_sequence(raw_images)
    total = len(sequence.items)
    for index, item in enumerate(sequence.items, start=1):
        parameters = parameters_by_path.get(item.relative_path)
        if parameters is None:
            raise ValueError(f"Missing colour parameters for {item.relative_path}")
        if progress:
            progress(index, total, item.relative_path)
        correct_image_file(
            source=raw_images / item.relative_path,
            destination=recoloured_images / item.relative_path,
            parameters=parameters,
        )
    return corrected_tree_status(raw_images=raw_images, recoloured_images=recoloured_images)


def apply_state_corrections(
    *,
    state: ColourRestorationState,
    run_dir: Path,
    overwrite_existing: bool = False,
    progress: Callable[[int, int, Path], None] | None = None,
) -> ColourRestorationState:
    """Apply corrections from edited keyframes and persist completion state."""
    state_path = colour_state_path(run_dir)
    edited_keyframes = [keyframe for keyframe in state.keyframes if keyframe.edited and keyframe.parameters is not None]
    unedited_keyframes = len(state.keyframes) - len(edited_keyframes)
    if state.output_recoloured_root.exists() and any(state.output_recoloured_root.rglob("*")):
        if not overwrite_existing:
            status = corrected_tree_status(
                raw_images=state.source_raw_root,
                recoloured_images=state.output_recoloured_root,
            )
            if status.complete:
                adopted = _state_with_existing_recoloured_images(state=state, status=status)
                save_state(state_path, adopted)
                return adopted
            raise ValueError(
                "recoloured_images already contains incomplete or inconsistent outputs; rerun with explicit overwrite "
                "confirmation because the current corrected version will be overwritten"
            )
        shutil.rmtree(state.output_recoloured_root)
    if not edited_keyframes:
        failed_payload = state.with_status(ColourStatus.FAILED, active_session=False).to_dict()
        failed_payload["error"] = {
            "message": "At least one edited keyframe is required to apply colour restoration",
            "failed_image": None,
        }
        failed = ColourRestorationState.from_dict(failed_payload)
        save_state(state_path, failed)
        raise ValueError("At least one edited keyframe is required to apply colour restoration")
    applying = state.with_status(ColourStatus.APPLYING, active_session=True)
    save_state(state_path, applying)
    failed_image: Path | None = None
    try:
        sequence = build_image_sequence(state.source_raw_root)
        parameters_by_path = interpolate_parameters(sequence, state.keyframes)
        interpolation = {
            "mode": state.mode,
            "ordering_method": sequence.ordering_method,
            "total_images": len(sequence.items),
            "edited_keyframes": len(edited_keyframes),
            "unedited_keyframes": unedited_keyframes,
            "keyframe_relative_paths": [keyframe.relative_path.as_posix() for keyframe in edited_keyframes],
        }

        def _progress(index: int, total: int, relative_path: Path) -> None:
            nonlocal failed_image
            failed_image = relative_path
            if progress:
                progress(index, total, relative_path)

        status = apply_corrections(
            raw_images=state.source_raw_root,
            recoloured_images=state.output_recoloured_root,
            parameters_by_path=parameters_by_path,
            progress=_progress,
        )
        if not status.complete:
            raise ValueError("Corrected image output validation failed")
        completed = ColourRestorationState.from_dict(
            {
                **applying.with_status(ColourStatus.COMPLETE, active_session=False).to_dict(),
                "interpolation": {
                    **interpolation,
                    "output_validation": {
                        "missing": [path.as_posix() for path in status.missing],
                        "extra": [path.as_posix() for path in status.extra],
                        "dimension_mismatches": status.dimension_mismatches,
                        "mode_mismatches": status.mode_mismatches,
                    },
                },
                "error": None,
            }
        )
        save_state(state_path, completed)
        return completed
    except Exception as exc:
        failed_payload = applying.with_status(ColourStatus.FAILED, active_session=False).to_dict()
        failed_payload["error"] = {"message": str(exc), "failed_image": failed_image.as_posix() if failed_image else None}
        failed = ColourRestorationState.from_dict(failed_payload)
        save_state(state_path, failed)
        raise


def assert_colour_ready_for_handoff(*, run_dir: Path, require_complete: bool) -> ColourRestorationState | None:
    """Return colour state or fail when colour-restored handoff is not ready."""
    if not require_complete:
        return None
    path = colour_state_path(run_dir)
    if not path.exists():
        raise ValueError(f"Colour restoration state is missing: {path}")
    state = load_state(path)
    if state.status == ColourStatus.SKIPPED:
        return state
    if state.status != ColourStatus.COMPLETE or state.active_session:
        raise ValueError(
            "Colour restoration is not complete; corrected images cannot be used for the final undistorted handoff"
        )
    status = corrected_tree_status(
        raw_images=state.source_raw_root,
        recoloured_images=state.output_recoloured_root,
    )
    if not status.complete:
        raise ValueError("Corrected image output tree is incomplete or inconsistent")
    return state
