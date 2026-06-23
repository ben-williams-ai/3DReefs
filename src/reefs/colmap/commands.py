"""COLMAP 4.0.4 command builders for the SfM pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from reefs.config.models import PipelineConfig
from reefs.preflight.images import ImageLayout


@dataclass(frozen=True)
class ColmapCommand:
    """A COLMAP command ready for subprocess execution."""

    stage: str
    args: list[str]

    @property
    def command_name(self) -> str:
        """Return the COLMAP subcommand name."""
        return self.args[1] if len(self.args) > 1 else ""


def bool_flag(value: bool) -> str:
    """Return COLMAP-compatible boolean flags."""
    return "1" if value else "0"


def matching_passes(mode: str) -> list[str]:
    """Expand a user-facing matching mode into ordered COLMAP matcher passes."""
    if mode == "exhaustive":
        return ["exhaustive"]
    if mode == "sequential":
        return ["sequential"]
    if mode == "vocab_tree":
        return ["vocab_tree"]
    if mode == "spatial":
        return ["spatial"]
    if mode == "sequential_vocab_tree":
        return ["sequential", "vocab_tree"]
    if mode == "hybrid":
        return ["sequential", "vocab_tree"]
    raise ValueError(f"Unsupported matching mode: {mode}")


def matching_requires_vocab_tree(mode: str) -> bool:
    """Return whether a matching mode needs a vocabulary tree file."""
    return "vocab_tree" in matching_passes(mode)


def matching_requires_pose_priors(mode: str) -> bool:
    """Return whether a matching mode needs pose priors."""
    return "spatial" in matching_passes(mode)


def _append_options(args: list[str], options: dict[str, object] | None) -> None:
    if not options:
        return
    for key, value in options.items():
        args.extend([f"--{key}", str(value)])


def build_feature_extractor(
    *,
    config: PipelineConfig,
    layout: ImageLayout,
    database_path: Path,
    image_path: Path,
    max_num_features: int,
    camera_params: str | None = None,
) -> ColmapCommand:
    """Build the feature extraction command."""
    sfm = config.advanced.sfm
    args = [
        config.tools.colmap_bin,
        "feature_extractor",
        "--database_path",
        str(database_path),
        "--image_path",
        str(image_path),
        "--ImageReader.camera_model",
        sfm.intrinsics.camera_model,
        "--ImageReader.single_camera",
        bool_flag(layout.kind == "single"),
        "--ImageReader.single_camera_per_folder",
        bool_flag(layout.kind == "multi"),
        "--FeatureExtraction.use_gpu",
        bool_flag(sfm.feature_extraction.use_gpu),
        "--FeatureExtraction.gpu_index",
        str(sfm.feature_extraction.gpu_index),
        "--SiftExtraction.max_num_features",
        str(max_num_features),
        "--SiftExtraction.first_octave",
        str(sfm.feature_extraction.sift.first_octave),
        "--SiftExtraction.num_octaves",
        str(sfm.feature_extraction.sift.num_octaves),
        "--SiftExtraction.octave_resolution",
        str(sfm.feature_extraction.sift.octave_resolution),
        "--SiftExtraction.peak_threshold",
        str(sfm.feature_extraction.sift.peak_threshold),
        "--SiftExtraction.edge_threshold",
        str(sfm.feature_extraction.sift.edge_threshold),
        "--SiftExtraction.max_num_orientations",
        str(sfm.feature_extraction.sift.max_num_orientations),
        "--SiftExtraction.estimate_affine_shape",
        bool_flag(sfm.feature_extraction.sift.estimate_affine_shape),
        "--SiftExtraction.upright",
        bool_flag(sfm.feature_extraction.sift.upright),
    ]
    if sfm.feature_extraction.max_image_size is not None:
        args.extend(["--FeatureExtraction.max_image_size", str(sfm.feature_extraction.max_image_size)])
    if camera_params and layout.kind == "single":
        args.extend(["--ImageReader.camera_params", camera_params])
    return ColmapCommand(stage="sfm.extract", args=args)


def build_matcher_commands(
    *,
    config: PipelineConfig,
    database_path: Path,
    vocab_tree_path: Path | None,
) -> list[ColmapCommand]:
    """Build ordered matcher commands for the configured matching mode."""
    sfm = config.advanced.sfm
    commands: list[ColmapCommand] = []
    for matching_pass in matching_passes(sfm.matching.mode):
        base = [
            config.tools.colmap_bin,
            f"{matching_pass}_matcher",
            "--database_path",
            str(database_path),
            "--FeatureMatching.use_gpu",
            bool_flag(sfm.matching.use_gpu),
            "--FeatureMatching.gpu_index",
            str(sfm.matching.gpu_index),
        ]
        if matching_pass == "sequential":
            loop = sfm.matching.sequential.loop_detection
            base.extend(
                [
                    "--SequentialMatching.overlap",
                    str(sfm.matching.sequential.overlap),
                    "--SequentialMatching.quadratic_overlap",
                    bool_flag(sfm.matching.sequential.quadratic_overlap),
                    "--SequentialMatching.loop_detection",
                    bool_flag(loop.enabled),
                    "--SequentialMatching.loop_detection_period",
                    str(loop.period),
                    "--SequentialMatching.loop_detection_num_images",
                    str(loop.num_images),
                    "--SequentialMatching.loop_detection_num_nearest_neighbors",
                    str(loop.num_nearest_neighbors),
                    "--SequentialMatching.loop_detection_num_checks",
                    str(loop.num_checks),
                ]
            )
            if loop.enabled and vocab_tree_path is not None:
                base.extend(["--SequentialMatching.vocab_tree_path", str(vocab_tree_path)])
        elif matching_pass == "vocab_tree":
            if vocab_tree_path is None:
                raise ValueError("Vocabulary-tree matching requires tools.vocab_tree_path")
            base.extend(
                [
                    "--VocabTreeMatching.vocab_tree_path",
                    str(vocab_tree_path),
                    "--VocabTreeMatching.num_images",
                    str(sfm.matching.vocab_tree.num_images),
                    "--VocabTreeMatching.num_nearest_neighbors",
                    str(sfm.matching.vocab_tree.num_nearest_neighbors),
                    "--VocabTreeMatching.num_checks",
                    str(sfm.matching.vocab_tree.num_checks),
                ]
            )
        elif matching_pass == "spatial":
            spatial = sfm.matching.spatial
            base.extend(["--SpatialMatching.ignore_z", bool_flag(spatial.ignore_z)])
            if spatial.max_num_neighbors is not None:
                base.extend(["--SpatialMatching.max_num_neighbors", str(spatial.max_num_neighbors)])
            if spatial.min_num_neighbors is not None:
                base.extend(["--SpatialMatching.min_num_neighbors", str(spatial.min_num_neighbors)])
            if spatial.max_distance is not None:
                base.extend(["--SpatialMatching.max_distance", str(spatial.max_distance)])
        commands.append(ColmapCommand(stage=f"sfm.match.{matching_pass}", args=base))
    return commands


def build_reconstruction_command(
    *,
    config: PipelineConfig,
    database_path: Path,
    image_path: Path,
    output_path: Path,
) -> ColmapCommand:
    """Build the selected sparse reconstruction command."""
    sfm = config.advanced.sfm
    if sfm.reconstruction.backend == "global":
        prefix = "GlobalMapper"
        subcommand = "global_mapper"
        gpu_options = {
            f"{prefix}.gp_use_gpu": sfm.reconstruction.use_gpu,
            f"{prefix}.ba_ceres_use_gpu": sfm.reconstruction.use_gpu,
        }
    elif sfm.reconstruction.backend == "incremental":
        prefix = "Mapper"
        subcommand = "mapper"
        gpu_options = {f"{prefix}.ba_use_gpu": sfm.reconstruction.use_gpu}
    else:
        raise ValueError(f"Unsupported reconstruction backend: {sfm.reconstruction.backend}")

    args = [
        config.tools.colmap_bin,
        subcommand,
        "--database_path",
        str(database_path),
        "--image_path",
        str(image_path),
        "--output_path",
        str(output_path),
        f"--{prefix}.ba_refine_focal_length",
        bool_flag(sfm.intrinsics.refine.refine_focal_length),
        f"--{prefix}.ba_refine_principal_point",
        bool_flag(sfm.intrinsics.refine.refine_principal_point),
        f"--{prefix}.ba_refine_extra_params",
        bool_flag(sfm.intrinsics.refine.refine_extra_params),
    ]
    for key, value in gpu_options.items():
        args.extend([f"--{key}", bool_flag(value)])
    _append_options(args, sfm.reconstruction.options)
    return ColmapCommand(stage="sfm.reconstruct", args=args)


def build_undistorter_command(
    *,
    config: PipelineConfig,
    image_path: Path,
    input_path: Path,
    output_path: Path,
) -> ColmapCommand:
    """Build the image undistortion command."""
    return ColmapCommand(
        stage="sfm.undistort",
        args=[
            config.tools.colmap_bin,
            "image_undistorter",
            "--image_path",
            str(image_path),
            "--input_path",
            str(input_path),
            "--output_path",
            str(output_path),
            "--output_type",
            "COLMAP",
            "--max_image_size",
            str(config.advanced.sfm.undistortion.max_image_size),
        ],
    )


def _build_patch_match_command(
    *,
    config: PipelineConfig,
    workspace_path: Path,
    stage: str,
    geom_consistency: bool,
) -> ColmapCommand:
    """Build one PatchMatch command for photometric or geometric dense stereo."""
    sfm = config.advanced.sfm
    return ColmapCommand(
        stage=stage,
        args=[
            config.tools.colmap_bin,
            "patch_match_stereo",
            "--workspace_path",
            str(workspace_path),
            "--workspace_format",
            "COLMAP",
            "--PatchMatchStereo.max_image_size",
            str(sfm.dense.patch_match.max_image_size),
            "--PatchMatchStereo.geom_consistency",
            bool_flag(geom_consistency),
        ],
    )


def build_dense_commands(*, config: PipelineConfig, workspace_path: Path) -> list[ColmapCommand]:
    """Build optional dense reconstruction commands."""
    sfm = config.advanced.sfm
    commands = [
        _build_patch_match_command(
            config=config,
            workspace_path=workspace_path,
            stage=(
                "sfm.dense.patch_match.photometric"
                if sfm.dense.patch_match.geom_consistency
                else "sfm.dense.patch_match"
            ),
            geom_consistency=False,
        ),
    ]
    if sfm.dense.patch_match.geom_consistency:
        commands.append(
            _build_patch_match_command(
                config=config,
                workspace_path=workspace_path,
                stage="sfm.dense.patch_match.geometric",
                geom_consistency=True,
            )
        )
    commands.append(
        ColmapCommand(
            stage="sfm.dense.fusion",
            args=[
                config.tools.colmap_bin,
                "stereo_fusion",
                "--workspace_path",
                str(workspace_path),
                "--workspace_format",
                "COLMAP",
                "--input_type",
                "geometric" if sfm.dense.patch_match.geom_consistency else "photometric",
                "--output_path",
                str(workspace_path / "fused.ply"),
                "--StereoFusion.min_num_pixels",
                str(sfm.dense.fusion.min_num_pixels),
                "--StereoFusion.max_reproj_error",
                str(sfm.dense.fusion.max_reproj_error),
                "--StereoFusion.max_depth_error",
                str(sfm.dense.fusion.max_depth_error),
                "--StereoFusion.max_normal_error",
                str(sfm.dense.fusion.max_normal_error),
            ],
        ),
    )
    if sfm.dense.mesh.enabled:
        if sfm.dense.mesh.method == "delaunay":
            commands.append(
                ColmapCommand(
                    stage="sfm.mesh",
                    args=[
                        config.tools.colmap_bin,
                        "delaunay_mesher",
                        "--input_path",
                        str(workspace_path),
                        "--input_type",
                        "dense",
                        "--output_path",
                        str(workspace_path / "meshed-delaunay.ply"),
                    ],
                )
            )
        else:
            commands.append(
                ColmapCommand(
                    stage="sfm.mesh",
                    args=[
                        config.tools.colmap_bin,
                        "poisson_mesher",
                        "--input_path",
                        str(workspace_path / "fused.ply"),
                        "--output_path",
                        str(workspace_path / "meshed-poisson.ply"),
                        "--PoissonMeshing.depth",
                        str(sfm.dense.mesh.poisson_depth),
                    ],
                )
            )
    return commands


def command_names(commands: Iterable[ColmapCommand]) -> list[str]:
    """Return command names for diagnostics and tests."""
    return [command.command_name for command in commands]
