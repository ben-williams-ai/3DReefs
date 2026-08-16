"""Colour restoration orchestration and output validation."""

from __future__ import annotations

import shutil
import os
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Callable

from reefs.colour.filters import ColourParameterSet, apply_colour_filters
from reefs.colour.interpolation import interpolate_parameters
from reefs.colour.ordering import build_image_sequence
from reefs.colour.state import ColourRestorationState, ColourStatus, load_state, save_state
from reefs.colour.profile import load_profile, profile_parameters, profile_sha256


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


class ColourImageCorrectionError(RuntimeError):
    """Image correction failure carrying the source relative path."""

    def __init__(self, relative_path: Path, original: Exception):
        self.relative_path = relative_path
        super().__init__(f"{relative_path.as_posix()}: {original}")


EXISTING_RECOLOURED_IMAGES_MESSAGE = (
    "Found existing complete same-run recoloured_images/; using it for splatting inputs."
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
    restoration_mode: str | None = None,
    overwrite: bool = False,
    start_sfm_immediately: bool = True,
) -> ColourRestorationState:
    """Create an initial colour restoration state for a run."""
    sequence = build_image_sequence(raw_images)
    return ColourRestorationState(
        run_id=run_id,
        source_raw_root=raw_images,
        output_recoloured_root=recoloured_images,
        ordering_method=sequence.ordering_method,
        ordering_warnings=sequence.ordering_warnings,
        restoration_mode=restoration_mode,
        sfm_image_source="raw",
        splat_image_source="recoloured" if restoration_mode in {"gray_world", "manual"} else None,
        splat_images_path=recoloured_images if restoration_mode in {"gray_world", "manual"} else None,
        relevant_config={
            "state_path": str(colour_state_path(run_dir)),
            "mode": restoration_mode,
            "overwrite": overwrite,
            "start_sfm_immediately": start_sfm_immediately,
        },
    )


def load_or_initialise_state(
    *,
    run_id: str,
    run_dir: Path,
    raw_images: Path,
    recoloured_images: Path,
    restoration_mode: str | None = None,
    overwrite: bool = False,
    start_sfm_immediately: bool = True,
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
        restoration_mode=restoration_mode,
        overwrite=overwrite,
        start_sfm_immediately=start_sfm_immediately,
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


def corrected_workspace_path(run_dir: Path, workspace: Path) -> Path:
    """Return the corrected image tree for one named SfM workspace."""
    return run_dir / "colour_restoration" / "outputs" / workspace.name / "images"


def _workspace_mapping(
    run_dir: Path,
    source_images: Path,
    original_names: list[str],
    dataset_fingerprint: str,
) -> dict[Path, Path]:
    mapping_path = run_dir / "sfm" / "image_mapping.json"
    if mapping_path.exists():
        data = json.loads(mapping_path.read_text(encoding="utf-8"))
        recorded_fingerprint = data.get("dataset_fingerprint")
        if recorded_fingerprint and recorded_fingerprint != dataset_fingerprint:
            raise ValueError("Colour profile dataset fingerprint does not match the SfM source")
        entries = data.get("entries", [])
        mapping = {Path(item["original"]): Path(item["staged"]) for item in entries}
        if set(mapping) != {Path(name) for name in original_names}:
            raise ValueError("Colour profile dataset does not match the SfM image mapping")
        return mapping
    available = {
        path.relative_to(source_images)
        for path in source_images.rglob("*")
        if path.is_file()
    }
    expected = {Path(name) for name in original_names}
    if available <= expected:
        return {path: path for path in expected}

    def safe_part(value: str) -> str:
        cleaned = "".join(character.lower() if character.isalnum() else "_" for character in value)
        cleaned = "_".join(part for part in cleaned.split("_") if part) or "image"
        suffix = hashlib.blake2s(value.encode("utf-8", errors="surrogatepass"), digest_size=4).hexdigest()
        return f"{cleaned}_{suffix}"

    reconstructed: dict[Path, Path] = {}
    counters: dict[Path, int] = {}
    for name in original_names:
        original = Path(name)
        parent = original.parent if original.parent != Path(".") else Path()
        staged_parent = Path(*[safe_part(part) for part in parent.parts]) if parent.parts else Path()
        counters[staged_parent] = counters.get(staged_parent, 0) + 1
        digest = hashlib.blake2s(name.encode("utf-8", errors="surrogatepass"), digest_size=4).hexdigest()
        reconstructed[original] = staged_parent / (
            f"img_{counters[staged_parent]:06d}_{digest}{original.suffix.lower() or '.jpg'}"
        )
    if not available <= set(reconstructed.values()):
        raise ValueError(
            "Undistorted image names differ from the colour profile and no exact SfM image mapping exists"
        )
    return reconstructed


def prepare_corrected_workspace(
    *,
    run_dir: Path,
    workspace: Path,
    mode: str,
    profile_path: Path | None,
    overwrite: bool,
    progress: Callable[[int, int, Path], None] | None = None,
) -> Path:
    """Atomically create corrected copies of one undistorted workspace."""
    source_images = workspace / "images"
    if not source_images.is_dir():
        raise ValueError(f"Undistorted image workspace is missing: {source_images}")
    output = corrected_workspace_path(run_dir, workspace)
    output_root = output.parent
    manifest_path = output_root / "manifest.json"
    source_names = {
        path.relative_to(source_images)
        for path in source_images.rglob("*")
        if path.is_file()
    }
    profile_digest = "gray_world"
    if mode == "profile":
        if profile_path is None:
            raise ValueError("A colour profile path is required")
        profile = load_profile(profile_path)
        profile_digest = profile_sha256(profile_path)
        original_parameters = profile_parameters(profile)
        original_names = [str(item["relative_path"]) for item in profile.ordered_images]
        mapping = _workspace_mapping(
            run_dir,
            source_images,
            original_names,
            profile.dataset_fingerprint,
        )
        parameters = {
            mapping[path]: value
            for path, value in original_parameters.items()
            if mapping[path] in source_names
        }
    elif mode == "gray_world":
        parameters = {
            path.relative_to(source_images): ColourParameterSet(gray_world=1.0)
            for path in source_images.rglob("*")
            if path.is_file()
        }
    else:
        raise ValueError(f"Unsupported corrected workspace mode: {mode}")

    if set(parameters) != source_names:
        raise ValueError("Colour profile does not map exactly to the undistorted workspace")
    inventory = hashlib.sha256()
    for relative_path in sorted(source_names):
        inventory.update(relative_path.as_posix().encode("utf-8"))
        with (source_images / relative_path).open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                inventory.update(block)
    source_inventory = inventory.hexdigest()
    expected_manifest = {
        "status": "complete",
        "mode": mode,
        "profile_sha256": profile_digest,
        "source_workspace": str(workspace),
        "source_inventory": source_inventory,
        "image_count": len(source_names),
    }
    if output.exists() and manifest_path.exists() and not overwrite:
        if json.loads(manifest_path.read_text(encoding="utf-8")) == expected_manifest:
            status = corrected_tree_status(raw_images=source_images, recoloured_images=output)
            if status.complete:
                return output
        raise ValueError("Corrected undistorted output exists but is incompatible; enable overwrite")
    temporary_root = output_root.with_name(f".{output_root.name}.tmp")
    temporary = temporary_root / "images"
    if temporary_root.exists():
        shutil.rmtree(temporary_root)
    try:
        status = apply_corrections(
            raw_images=source_images,
            recoloured_images=temporary,
            parameters_by_path=parameters,
            progress=progress,
        )
        if not status.complete:
            raise ValueError("Corrected undistorted output validation failed")
        if output_root.exists():
            if not overwrite:
                raise ValueError("Corrected undistorted output already exists")
            shutil.rmtree(output_root)
        temporary_root.mkdir(parents=True, exist_ok=True)
        (temporary_root / "manifest.json").write_text(
            json.dumps(expected_manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        output_root.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temporary_root, output_root)
    except Exception:
        if temporary_root.exists():
            shutil.rmtree(temporary_root)
        raise
    return output


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
    """Persist same-run reuse metadata when completed outputs remain valid."""
    expected_mode = state.relevant_config.get("mode")
    if state.restoration_mode not in {"gray_world", "manual"}:
        return None
    if expected_mode is not None and state.restoration_mode != expected_mode:
        return None
    if state.status != ColourStatus.COMPLETE or state.active_session:
        return None
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
    completed["restoration_mode"] = state.restoration_mode
    completed["sfm_image_source"] = "raw"
    completed["splat_image_source"] = "recoloured"
    completed["splat_images_path"] = str(state.output_recoloured_root)
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
    worker_count = _colour_worker_count()

    def _correct_item(item) -> Path:
        parameters = parameters_by_path.get(item.relative_path)
        if parameters is None:
            raise ValueError(f"Missing colour parameters for {item.relative_path}")
        try:
            correct_image_file(
                source=raw_images / item.relative_path,
                destination=recoloured_images / item.relative_path,
                parameters=parameters,
            )
        except Exception as exc:
            raise ColourImageCorrectionError(item.relative_path, exc) from exc
        return item.relative_path

    if worker_count <= 1 or total <= 1:
        for index, item in enumerate(sequence.items, start=1):
            relative_path = _correct_item(item)
            if progress:
                progress(index, total, relative_path)
        return corrected_tree_status(raw_images=raw_images, recoloured_images=recoloured_images)

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [(item.relative_path, executor.submit(_correct_item, item)) for item in sequence.items]
        for index, (relative_path, future) in enumerate(futures, start=1):
            try:
                future.result()
            except Exception as exc:
                if isinstance(exc, ColourImageCorrectionError):
                    raise
                raise ColourImageCorrectionError(relative_path, exc) from exc
            if progress:
                progress(index, total, relative_path)
    return corrected_tree_status(raw_images=raw_images, recoloured_images=recoloured_images)


def _colour_worker_count() -> int:
    """Return bounded worker count for full-resolution colour writes."""
    configured = os.environ.get("REEFS_COLOUR_WORKERS")
    if configured:
        try:
            return max(1, int(configured))
        except ValueError:
            return 1
    return min(8, os.cpu_count() or 1)


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
            adopted = adopt_existing_recoloured_images(state=state, run_dir=run_dir)
            if adopted is not None:
                return adopted
            raise ValueError(
                "recoloured_images already contains outputs that are not reusable for this same-run manual state; "
                "rerun with explicit overwrite confirmation because the current corrected version will be overwritten"
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
                "restoration_mode": state.restoration_mode or "manual",
                "sfm_image_source": "raw",
                "splat_image_source": "recoloured",
                "splat_images_path": str(state.output_recoloured_root),
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
        if isinstance(exc, ColourImageCorrectionError):
            failed_image = exc.relative_path
        failed_payload = applying.with_status(ColourStatus.FAILED, active_session=False).to_dict()
        failed_payload["error"] = {"message": str(exc), "failed_image": failed_image.as_posix() if failed_image else None}
        failed = ColourRestorationState.from_dict(failed_payload)
        save_state(state_path, failed)
        raise


def apply_gray_world_restoration(
    *,
    state: ColourRestorationState,
    run_dir: Path,
    overwrite_existing: bool = False,
    progress: Callable[[int, int, Path], None] | None = None,
) -> ColourRestorationState:
    """Apply automatic gray-world restoration to every source image."""
    state_path = colour_state_path(run_dir)
    if state.output_recoloured_root.exists() and any(state.output_recoloured_root.rglob("*")):
        if not overwrite_existing:
            adopted = adopt_existing_recoloured_images(state=state, run_dir=run_dir)
            if adopted is not None:
                return adopted
            raise ValueError(
                "recoloured_images already contains incomplete or incompatible outputs; "
                "enable colour_restoration.overwrite to regenerate them"
            )
        shutil.rmtree(state.output_recoloured_root)
    applying = state.with_status(ColourStatus.APPLYING, active_session=False)
    applying = ColourRestorationState.from_dict(
        {
            **applying.to_dict(),
            "restoration_mode": "gray_world",
            "sfm_image_source": "raw",
            "splat_image_source": "recoloured",
            "splat_images_path": str(state.output_recoloured_root),
        }
    )
    save_state(state_path, applying)
    failed_image: Path | None = None
    try:
        sequence = build_image_sequence(state.source_raw_root)
        parameters = ColourParameterSet(gray_world=1.0)
        parameters_by_path = {item.relative_path: parameters for item in sequence.items}

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
            raise ValueError("Gray-world image output validation failed")
        completed = ColourRestorationState.from_dict(
            {
                **applying.with_status(ColourStatus.COMPLETE, active_session=False).to_dict(),
                "restoration_mode": "gray_world",
                "sfm_image_source": "raw",
                "splat_image_source": "recoloured",
                "splat_images_path": str(state.output_recoloured_root),
                "interpolation": {
                    "mode": "gray_world",
                    "gray_world": 1.0,
                    "ordering_method": sequence.ordering_method,
                    "total_images": len(sequence.items),
                    "output_validation": {
                        "missing": [path.as_posix() for path in status.missing],
                        "extra": [path.as_posix() for path in status.extra],
                        "dimension_mismatches": status.dimension_mismatches,
                        "mode_mismatches": status.mode_mismatches,
                    },
                },
                "relevant_config": {
                    **applying.relevant_config,
                    "mode": "gray_world",
                    "regenerated_recoloured_images": overwrite_existing,
                },
                "error": None,
            }
        )
        save_state(state_path, completed)
        return completed
    except Exception as exc:
        if isinstance(exc, ColourImageCorrectionError):
            failed_image = exc.relative_path
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
            "Colour restoration is not complete; restored images cannot be used for splatting inputs"
        )
    if (run_dir / "colour_restoration" / "profile.json").is_file():
        return state
    status = corrected_tree_status(
        raw_images=state.source_raw_root,
        recoloured_images=state.output_recoloured_root,
    )
    if not status.complete:
        raise ValueError("Corrected image output tree is incomplete or inconsistent")
    return state
