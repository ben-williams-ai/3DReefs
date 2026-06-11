"""COLMAP SfM pipeline orchestration."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from reefs.colmap.commands import (
    ColmapCommand,
    build_dense_commands,
    build_feature_extractor,
    build_matcher_commands,
    build_reconstruction_command,
    build_undistorter_command,
)
from reefs.colmap.outputs import SparseModelSummary, list_sparse_models, select_sparse_model
from reefs.colmap.runner import CommandResult, run_colmap_command
from reefs.logging.timings import TimingRecorder
from reefs.preflight.images import ImageLayout
from reefs.preflight.sfm import SfMPreflightResult
from reefs.sfm.validation import SfMPaths, create_sfm_paths, expand_sfm_steps
from reefs.sfm.intrinsics import camera_params_from_cameras_txt


@dataclass
class SfMRunResult:
    """Outputs and metadata from an SfM invocation."""

    paths: SfMPaths
    command_results: list[CommandResult] = field(default_factory=list)
    sparse_models: list[SparseModelSummary] = field(default_factory=list)
    selected_sparse_model: SparseModelSummary | None = None
    output_paths: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable result."""
        return {
            "database_path": str(self.paths.database),
            "sparse_root": str(self.paths.sparse),
            "selected_sparse_model": self.selected_sparse_model.as_dict()
            if self.selected_sparse_model
            else None,
            "sparse_models": [summary.as_dict() for summary in self.sparse_models],
            "output_paths": self.output_paths,
            "warnings": self.warnings,
            "commands": [result.as_dict() for result in self.command_results],
        }


def effective_max_num_features(*, configured: int, total_images: int) -> int:
    """Apply the configured large-collection protective feature count."""
    if total_images > 10000 and configured == 8192:
        return 4096
    return configured


def _run(command: ColmapCommand, *, paths: SfMPaths, timings: TimingRecorder) -> CommandResult:
    with timings.stage(command.stage):
        return run_colmap_command(command, log_path=paths.colmap_log)


def _copy_selected_sparse(selected: SparseModelSummary, destination: Path) -> Path:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(selected.path, destination)
    return destination


def _prepare_intrinsics_subset(*, source_root: Path, selected_images: dict[str, list[str]], target_root: Path) -> None:
    """Create a symlinked image subset for intrinsics pre-calculation."""
    if target_root.exists():
        shutil.rmtree(target_root)
    target_root.mkdir(parents=True)
    for images in selected_images.values():
        for relative_name in images:
            relative_path = Path(relative_name)
            target_path = target_root / relative_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.symlink_to((source_root / relative_path).resolve())


def _export_sparse_text(*, colmap_bin: str, input_path: Path, output_path: Path, paths: SfMPaths, timings: TimingRecorder) -> None:
    output_path.mkdir(parents=True, exist_ok=True)
    command = ColmapCommand(
        stage="sfm.reconstruct.export_text",
        args=[
            colmap_bin,
            "model_converter",
            "--input_path",
            str(input_path),
            "--output_path",
            str(output_path),
            "--output_type",
            "TXT",
        ],
    )
    _run(command, paths=paths, timings=timings)


def _with_refined_intrinsics(command: ColmapCommand) -> ColmapCommand:
    """Return a reconstruction command with intrinsics refinement enabled."""
    args = list(command.args)
    for flag in [
        "--GlobalMapper.ba_refine_focal_length",
        "--GlobalMapper.ba_refine_principal_point",
        "--GlobalMapper.ba_refine_extra_params",
        "--Mapper.ba_refine_focal_length",
        "--Mapper.ba_refine_principal_point",
        "--Mapper.ba_refine_extra_params",
    ]:
        if flag in args:
            args[args.index(flag) + 1] = "1"
    return ColmapCommand(stage="sfm.intrinsics.reconstruct", args=args)


def _run_intrinsics_precalculation(
    *,
    config,
    derived_paths,
    layout: ImageLayout,
    paths: SfMPaths,
    preflight_result: SfMPreflightResult,
    max_num_features: int,
    timings: TimingRecorder,
) -> tuple[str | None, list[CommandResult]]:
    """Run a subset reconstruction to estimate camera parameters."""
    selection = preflight_result.intrinsics_selection
    if selection.source == "user_cameras_file":
        return selection.camera_params, []
    if selection.source != "precalculated":
        return None, []

    subset_root = paths.root / "intrinsics_subset" / "images"
    subset_database = paths.root / "intrinsics_subset" / "database.db"
    subset_sparse = paths.root / "intrinsics_subset" / "sparse"
    subset_selected = paths.root / "intrinsics_subset" / "selected_sparse"
    subset_text = paths.root / "intrinsics_subset" / "selected_sparse_txt"
    _prepare_intrinsics_subset(
        source_root=derived_paths.raw_images,
        selected_images=selection.selected_images,
        target_root=subset_root,
    )
    subset_sparse.mkdir(parents=True, exist_ok=True)
    results: list[CommandResult] = []
    feature_command = build_feature_extractor(
        config=config,
        layout=layout,
        database_path=subset_database,
        image_path=subset_root,
        max_num_features=max_num_features,
        camera_params=None,
    )
    results.append(_run(ColmapCommand(stage="sfm.intrinsics.extract", args=feature_command.args), paths=paths, timings=timings))
    for command in build_matcher_commands(
        config=config,
        database_path=subset_database,
        vocab_tree_path=config.tools.vocab_tree_path,
    ):
        results.append(
            _run(
                ColmapCommand(stage=command.stage.replace("sfm.match", "sfm.intrinsics.match"), args=command.args),
                paths=paths,
                timings=timings,
            )
        )
    reconstruction_command = build_reconstruction_command(
        config=config,
        database_path=subset_database,
        image_path=subset_root,
        output_path=subset_sparse,
    )
    results.append(_run(_with_refined_intrinsics(reconstruction_command), paths=paths, timings=timings))
    selected = select_sparse_model(list_sparse_models(subset_sparse))
    _copy_selected_sparse(selected, subset_selected)
    _export_sparse_text(
        colmap_bin=config.tools.colmap_bin,
        input_path=subset_selected,
        output_path=subset_text,
        paths=paths,
        timings=timings,
    )
    return camera_params_from_cameras_txt(subset_text / "cameras.txt"), results


def _select_undistortion_image_root(*, config, derived_paths) -> tuple[Path, str]:
    setting = config.advanced.sfm.undistortion.image_source
    if setting == "raw":
        return derived_paths.raw_images, "raw"
    if setting == "recoloured":
        return derived_paths.recoloured_images, "recoloured"
    if config.project.recolour_images:
        return derived_paths.recoloured_images, "recoloured"
    return derived_paths.raw_images, "raw"


def run_sfm_pipeline(
    *,
    config,
    derived_paths,
    layout: ImageLayout,
    run_paths,
    preflight_result: SfMPreflightResult,
    requested_steps: list[str],
    timings: TimingRecorder,
) -> SfMRunResult:
    """Run requested COLMAP SfM stages."""
    sfm_paths = create_sfm_paths(run_paths)
    requested = set(expand_sfm_steps(requested_steps))
    run_all = "sfm" in requested_steps
    result = SfMRunResult(paths=sfm_paths, warnings=list(preflight_result.warnings))
    total_images = len(layout.relative_image_paths)
    max_num_features = effective_max_num_features(
        configured=config.advanced.sfm.feature_extraction.max_num_features,
        total_images=total_images,
    )

    camera_params = preflight_result.intrinsics_selection.camera_params
    if run_all or "sfm.intrinsics" in requested or "sfm.extract" in requested:
        params, intrinsics_results = _run_intrinsics_precalculation(
            config=config,
            derived_paths=derived_paths,
            layout=layout,
            paths=sfm_paths,
            preflight_result=preflight_result,
            max_num_features=max_num_features,
            timings=timings,
        )
        result.command_results.extend(intrinsics_results)
        camera_params = params or camera_params
        if camera_params:
            result.output_paths["intrinsics_camera_params"] = camera_params

    if run_all or "sfm.extract" in requested:
        command = build_feature_extractor(
            config=config,
            layout=layout,
            database_path=sfm_paths.database,
            image_path=derived_paths.raw_images,
            max_num_features=max_num_features,
            camera_params=camera_params,
        )
        result.command_results.append(_run(command, paths=sfm_paths, timings=timings))

    if run_all or "sfm.match" in requested:
        for command in build_matcher_commands(
            config=config,
            database_path=sfm_paths.database,
            vocab_tree_path=config.tools.vocab_tree_path,
        ):
            result.command_results.append(_run(command, paths=sfm_paths, timings=timings))

    if run_all or "sfm.reconstruct" in requested:
        command = build_reconstruction_command(
            config=config,
            database_path=sfm_paths.database,
            image_path=derived_paths.raw_images,
            output_path=sfm_paths.sparse,
        )
        result.command_results.append(_run(command, paths=sfm_paths, timings=timings))
        sparse_models = list_sparse_models(sfm_paths.sparse)
        selected = select_sparse_model(sparse_models)
        selected_sparse_path = _copy_selected_sparse(selected, sfm_paths.selected_sparse)
        _export_sparse_text(
            colmap_bin=config.tools.colmap_bin,
            input_path=selected_sparse_path,
            output_path=sfm_paths.selected_sparse_text,
            paths=sfm_paths,
            timings=timings,
        )
        text_summary = select_sparse_model(list_sparse_models(sfm_paths.selected_sparse_text))
        result.sparse_models = [
            SparseModelSummary(
                model_id=summary.model_id,
                path=summary.path,
                registered_images=summary.registered_images,
                points3d=summary.points3d,
                selected=summary.model_id == selected.model_id,
            )
            for summary in sparse_models
        ]
        result.selected_sparse_model = SparseModelSummary(
            model_id=selected.model_id,
            path=selected_sparse_path,
            registered_images=text_summary.registered_images,
            points3d=text_summary.points3d,
            selected=True,
        )
        if len(sparse_models) > 1:
            result.warnings.append(
                "Reconstruction produced multiple sparse models; selected the model with the most registered images."
            )

    if run_all or "sfm.undistort" in requested:
        if not sfm_paths.selected_sparse.exists():
            raise ValueError("Cannot undistort because selected sparse model is missing")
        image_root, image_source = _select_undistortion_image_root(config=config, derived_paths=derived_paths)
        command = build_undistorter_command(
            config=config,
            image_path=image_root,
            input_path=sfm_paths.selected_sparse,
            output_path=sfm_paths.undistorted,
        )
        result.command_results.append(_run(command, paths=sfm_paths, timings=timings))
        result.output_paths["sparse_image_source"] = "raw"
        result.output_paths["undistortion_image_source"] = image_source
        result.output_paths["undistorted_images"] = str(sfm_paths.undistorted / "images")
        result.output_paths["undistorted_sparse"] = str(sfm_paths.undistorted / "sparse")
        result.output_paths["undistorted_intrinsics"] = str(sfm_paths.undistorted / "sparse" / "cameras.bin")

    if config.advanced.sfm.dense.enabled and (run_all or "sfm.dense" in requested or "sfm.mesh" in requested):
        for command in build_dense_commands(config=config, workspace_path=sfm_paths.undistorted):
            result.command_results.append(_run(command, paths=sfm_paths, timings=timings))
        result.output_paths["dense_workspace"] = str(sfm_paths.undistorted)
        if config.advanced.sfm.dense.mesh.enabled:
            result.output_paths["mesh"] = str(sfm_paths.undistorted / "meshed-poisson.ply")

    return result
