"""SfM-specific preflight validation."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import click

from reefs.colmap.commands import matching_passes, matching_requires_pose_priors, matching_requires_vocab_tree
from reefs.diagnostics.cameras import CameraSourceReport, camera_source_reports
from reefs.diagnostics.images import CameraDimensionReport, dimension_reports, image_dimensions, write_dimension_report
from reefs.preflight.images import ImageLayout
from reefs.preflight.tools import run_tool_command
from reefs.runs.manifest import RunPaths
from reefs.sfm.intrinsics import IntrinsicsSelection, choose_intrinsics


@dataclass(frozen=True)
class SfMPreflightResult:
    """Validated SfM preflight data."""

    dimension_reports: list[CameraDimensionReport]
    camera_source_reports: list[CameraSourceReport]
    intrinsics_selection: IntrinsicsSelection
    warnings: list[str]

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable preflight result."""
        return {
            "dimension_reports": [report.as_dict() for report in self.dimension_reports],
            "camera_source_reports": [report.as_dict() for report in self.camera_source_reports],
            "intrinsics_selection": self.intrinsics_selection.as_dict(),
            "warnings": self.warnings,
        }


def _validate_recoloured_dimensions(*, raw_images: Path, recoloured_images: Path, layout: ImageLayout) -> None:
    mismatches: list[str] = []
    for relative_path in layout.relative_image_paths:
        raw_dim = image_dimensions(raw_images / relative_path)
        recoloured_dim = image_dimensions(recoloured_images / relative_path)
        if raw_dim != recoloured_dim:
            mismatches.append(f"{relative_path}: raw {raw_dim}, recoloured {recoloured_dim}")
    if mismatches:
        raise ValueError("Recoloured image dimensions differ from raw images: " + "; ".join(mismatches[:10]))


def _handle_mixed_camera_sources(
    reports: list[CameraSourceReport], *, proceed_setting: bool, interactive: bool
) -> list[str]:
    warnings: list[str] = []
    mixed = [report for report in reports if report.status == "mixed"]
    if not mixed:
        return warnings
    warning = (
        "Camera-source metadata suggests one or more camera folders contain images "
        "from different camera sources. Confirm the images are from the intended "
        "camera and have not been edited before continuing."
    )
    warnings.append(warning)
    if proceed_setting:
        warnings.append("Proceeding because advanced.sfm.preflight.proceed_on_mixed_camera_sources=true.")
        return warnings
    if not interactive:
        raise ValueError(
            "Mixed camera-source metadata detected in a non-interactive run. "
            "Set advanced.sfm.preflight.proceed_on_mixed_camera_sources=true only after checking the data."
        )
    if not click.confirm(warning + " Continue?", default=False):
        raise ValueError("Stopped because mixed camera-source warning was not confirmed")
    return warnings


def _validate_colmap_subcommands(*, colmap_bin: str, subcommands: list[str]) -> None:
    """Validate selected COLMAP subcommands exist without running heavy work."""
    for subcommand in subcommands:
        result = run_tool_command(colmap_bin, [subcommand, "-h"], timeout=5.0)
        if result.returncode not in {0, 1}:
            raise ValueError(f"COLMAP subcommand is unavailable or failed help validation: {subcommand}")


def validate_sfm_preflight(
    *,
    config,
    derived_paths,
    layout: ImageLayout,
    run_paths: RunPaths,
) -> SfMPreflightResult:
    """Validate SfM inputs before heavy COLMAP work starts."""
    sfm = config.advanced.sfm
    diagnostics_dir = run_paths.run_dir / "reports"
    reports = dimension_reports(raw_images=derived_paths.raw_images, layout=layout)
    if sfm.preflight.check_dimensions:
        invalid = [report for report in reports if not report.is_consistent]
        if invalid:
            report_path = diagnostics_dir / "image_dimension_report.md"
            write_dimension_report(reports, report_path)
            raise ValueError(
                "Image dimensions differ within a camera group. "
                f"Full report written to {report_path}"
            )

    source_reports = camera_source_reports(layout=layout) if sfm.preflight.check_camera_source_metadata else []
    warnings = _handle_mixed_camera_sources(
        source_reports,
        proceed_setting=sfm.preflight.proceed_on_mixed_camera_sources,
        interactive=sys.stdin.isatty(),
    )

    if matching_requires_vocab_tree(sfm.matching.mode):
        vocab_tree = config.tools.vocab_tree_path
        if vocab_tree is None or not Path(vocab_tree).exists():
            raise ValueError(
                "Selected SfM matching mode requires a valid tools.vocab_tree_path "
                f"(mode={sfm.matching.mode})"
            )
    if matching_requires_pose_priors(sfm.matching.mode) and not sfm.preflight.exif_pose_priors_enabled:
        raise ValueError("Spatial matching requires pose-prior support, which is disabled or unavailable")

    if sfm.reconstruction.validate_backend:
        reconstruction_command = "global_mapper" if sfm.reconstruction.backend == "global" else "mapper"
        matcher_commands = [f"{matching_pass}_matcher" for matching_pass in matching_passes(sfm.matching.mode)]
        subcommands = [
            "feature_extractor",
            *matcher_commands,
            reconstruction_command,
            "model_converter",
            "image_undistorter",
        ]
        if sfm.dense.enabled:
            subcommands.extend(["patch_match_stereo", "stereo_fusion"])
        if sfm.dense.mesh.enabled:
            subcommands.append("poisson_mesher")
        _validate_colmap_subcommands(colmap_bin=config.tools.colmap_bin, subcommands=sorted(set(subcommands)))

    intrinsics = choose_intrinsics(
        layout=layout,
        dimension_reports=reports,
        camera_model=sfm.intrinsics.camera_model,
        precalculate=sfm.intrinsics.precalculate,
        cameras_txt=sfm.intrinsics.cameras_txt,
        selection_start_index=sfm.intrinsics.selection_start_index,
        selection_end_index=sfm.intrinsics.selection_end_index,
    )
    warnings.extend(intrinsics.warnings)
    return SfMPreflightResult(
        dimension_reports=reports,
        camera_source_reports=source_reports,
        intrinsics_selection=intrinsics,
        warnings=warnings,
    )
