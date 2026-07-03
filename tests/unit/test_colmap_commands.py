"""Tests for COLMAP command construction."""

from __future__ import annotations

from pathlib import Path

from reefs.colmap.commands import (
    build_cross_camera_matcher_command,
    build_dense_commands,
    build_feature_extractor,
    build_matcher_commands,
    build_reconstruction_command,
    build_sparse_refinement_iteration_commands,
    command_names,
    matching_passes,
    matching_requires_vocab_tree,
)
from reefs.config.loader import load_config
from reefs.preflight.images import ImageLayout


def _config(tmp_path: Path):
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        f"""
colour_restoration:
  mode: off
  overwrite: false
  start_sfm_immediately: true

project:
  dir: {tmp_path}
tools:
  colmap_bin: colmap
  lfs_bin: LichtFeld-Studio
  splat_transform_bin: splat-transform
  vocab_tree_path: {tmp_path / "vocab.bin"}
""".lstrip(),
        encoding="utf-8",
    )
    return load_config(config_path)


def test_matching_mode_expands_to_sequential_then_vocab_tree() -> None:
    assert matching_passes("sequential_vocab_tree") == ["sequential", "vocab_tree"]
    assert matching_requires_vocab_tree("sequential_vocab_tree") is True


def test_feature_extractor_uses_multicamera_folder_mode(tmp_path: Path) -> None:
    config = _config(tmp_path)
    layout = ImageLayout(kind="multi", image_paths=[Path("cam1/a.jpg")], camera_dirs=["cam1"])

    command = build_feature_extractor(
        config=config,
        layout=layout,
        database_path=tmp_path / "database.db",
        image_path=tmp_path / "raw_images",
        max_num_features=8192,
    )

    assert "--ImageReader.single_camera_per_folder" in command.args
    assert command.args[command.args.index("--ImageReader.single_camera_per_folder") + 1] == "1"
    assert "--ImageReader.camera_model" in command.args
    assert "OPENCV" in command.args
    assert "--ImageReader.camera_params" not in command.args


def test_multicamera_feature_extractor_ignores_global_camera_params(tmp_path: Path) -> None:
    config = _config(tmp_path)
    layout = ImageLayout(kind="multi", image_paths=[Path("cam1/a.jpg")], camera_dirs=["cam1"])

    command = build_feature_extractor(
        config=config,
        layout=layout,
        database_path=tmp_path / "database.db",
        image_path=tmp_path / "raw_images",
        max_num_features=8192,
        camera_params="1,2,3,4,0,0,0,0",
    )

    assert "--ImageReader.single_camera_per_folder" in command.args
    assert command.args[command.args.index("--ImageReader.single_camera_per_folder") + 1] == "1"
    assert "--ImageReader.camera_params" not in command.args


def test_single_camera_feature_extractor_accepts_camera_params(tmp_path: Path) -> None:
    config = _config(tmp_path)
    layout = ImageLayout(kind="single", image_paths=[Path("a.jpg")], camera_dirs=[])

    command = build_feature_extractor(
        config=config,
        layout=layout,
        database_path=tmp_path / "database.db",
        image_path=tmp_path / "raw_images",
        max_num_features=8192,
        camera_params="1,2,3,4,0,0,0,0",
    )

    assert "--ImageReader.single_camera" in command.args
    assert command.args[command.args.index("--ImageReader.single_camera") + 1] == "1"
    assert command.args[command.args.index("--ImageReader.camera_params") + 1] == "1,2,3,4,0,0,0,0"


def test_default_matcher_uses_sequential_only(tmp_path: Path) -> None:
    config = _config(tmp_path)

    commands = build_matcher_commands(
        config=config,
        database_path=tmp_path / "database.db",
        vocab_tree_path=tmp_path / "vocab.bin",
    )

    assert command_names(commands) == ["sequential_matcher"]


def test_sequential_vocab_tree_mode_commands_are_ordered(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config.advanced.sfm.matching.mode = "sequential_vocab_tree"

    commands = build_matcher_commands(
        config=config,
        database_path=tmp_path / "database.db",
        vocab_tree_path=tmp_path / "vocab.bin",
    )

    assert command_names(commands) == ["sequential_matcher", "vocab_tree_matcher"]


def test_sequential_overlap_can_be_overridden_to_30(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config.advanced.sfm.matching.mode = "sequential"
    config.advanced.sfm.matching.sequential.overlap = 30

    command = build_matcher_commands(
        config=config,
        database_path=tmp_path / "database.db",
        vocab_tree_path=tmp_path / "vocab.bin",
    )[0]

    assert _option_value(command.args, "--SequentialMatching.overlap") == "30"


def test_feature_extractor_sift_shape_and_dsp_flags(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config.advanced.sfm.feature_extraction.sift.estimate_affine_shape = True
    config.advanced.sfm.feature_extraction.sift.domain_size_pooling = True
    layout = ImageLayout(kind="single", image_paths=[Path("a.jpg")], camera_dirs=[])

    command = build_feature_extractor(
        config=config,
        layout=layout,
        database_path=tmp_path / "database.db",
        image_path=tmp_path / "raw_images",
        max_num_features=8192,
    )

    assert _option_value(command.args, "--SiftExtraction.estimate_affine_shape") == "1"
    assert _option_value(command.args, "--SiftExtraction.domain_size_pooling") == "1"


def test_guided_matching_flag_reaches_matchers(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config.advanced.sfm.matching.guided_matching = True

    commands = build_matcher_commands(
        config=config,
        database_path=tmp_path / "database.db",
        vocab_tree_path=tmp_path / "vocab.bin",
    )

    assert [_option_value(command.args, "--FeatureMatching.guided_matching") for command in commands] == ["1"]


def test_cross_camera_matcher_uses_matches_importer_pairs(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config.advanced.sfm.matching.guided_matching = True

    command = build_cross_camera_matcher_command(
        config=config,
        database_path=tmp_path / "database.db",
        pairs_path=tmp_path / "pairs.txt",
    )

    assert command.command_name == "matches_importer"
    assert _option_value(command.args, "--match_type") == "pairs"
    assert _option_value(command.args, "--match_list_path") == str(tmp_path / "pairs.txt")
    assert _option_value(command.args, "--FeatureMatching.guided_matching") == "1"


def test_sparse_refinement_iteration_commands_use_colmap_flow(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config.advanced.sfm.sparse_refinement.point_filtering.max_reproj_error = 3.0
    config.advanced.sfm.sparse_refinement.bundle_adjuster.refine_principal_point = True

    commands, final_path = build_sparse_refinement_iteration_commands(
        config=config,
        database_path=tmp_path / "database.db",
        image_path=tmp_path / "raw_images",
        input_path=tmp_path / "selected_sparse",
        iteration_path=tmp_path / "refined_sparse" / "iter_01",
        iteration=1,
    )

    assert command_names(commands) == [
        "point_triangulator",
        "point_filtering",
        "bundle_adjuster",
        "model_analyzer",
    ]
    assert _option_value(commands[0].args, "--database_path") == str(tmp_path / "database.db")
    assert _option_value(commands[0].args, "--input_path") == str(tmp_path / "selected_sparse")
    assert _option_value(commands[1].args, "--input_path") == str(
        tmp_path / "refined_sparse" / "iter_01" / "triangulated"
    )
    assert _option_value(commands[1].args, "--max_reproj_error") == "3.0"
    assert _option_value(commands[2].args, "--BundleAdjustment.refine_principal_point") == "1"
    assert _option_value(commands[3].args, "--path") == str(final_path)
    assert final_path == tmp_path / "refined_sparse" / "iter_01" / "bundle_adjusted"


def test_global_reconstruction_uses_global_mapper(tmp_path: Path) -> None:
    config = _config(tmp_path)

    command = build_reconstruction_command(
        config=config,
        database_path=tmp_path / "database.db",
        image_path=tmp_path / "raw_images",
        output_path=tmp_path / "sparse",
    )

    assert command.command_name == "global_mapper"
    assert "--GlobalMapper.ba_refine_focal_length" in command.args
    assert command.args[command.args.index("--GlobalMapper.ba_refine_focal_length") + 1] == "1"


def _option_value(args: list[str], option: str) -> str:
    """Return the value following a COLMAP command-line option."""
    return args[args.index(option) + 1]


def test_reconstruction_refine_all_enables_all_intrinsics(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config.advanced.sfm.intrinsics.refine.all = True

    command = build_reconstruction_command(
        config=config,
        database_path=tmp_path / "database.db",
        image_path=tmp_path / "raw_images",
        output_path=tmp_path / "sparse",
    )

    assert _option_value(command.args, "--GlobalMapper.ba_refine_focal_length") == "1"
    assert _option_value(command.args, "--GlobalMapper.ba_refine_principal_point") == "1"
    assert _option_value(command.args, "--GlobalMapper.ba_refine_extra_params") == "1"


def test_reconstruction_refine_individual_switches_work_when_all_is_false(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config.advanced.sfm.intrinsics.refine.all = False
    config.advanced.sfm.intrinsics.refine.focal_length = True

    command = build_reconstruction_command(
        config=config,
        database_path=tmp_path / "database.db",
        image_path=tmp_path / "raw_images",
        output_path=tmp_path / "sparse",
    )

    assert _option_value(command.args, "--GlobalMapper.ba_refine_focal_length") == "1"
    assert _option_value(command.args, "--GlobalMapper.ba_refine_principal_point") == "0"
    assert _option_value(command.args, "--GlobalMapper.ba_refine_extra_params") == "0"


def test_dense_geometric_mode_runs_photometric_then_geometric_patch_match(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config.advanced.sfm.dense.enabled = True
    config.advanced.sfm.dense.patch_match.geom_consistency = True

    commands = build_dense_commands(config=config, workspace_path=tmp_path / "undistorted")

    assert [command.stage for command in commands[:3]] == [
        "sfm.dense.patch_match.photometric",
        "sfm.dense.patch_match.geometric",
        "sfm.dense.fusion",
    ]
    assert _option_value(commands[0].args, "--PatchMatchStereo.geom_consistency") == "0"
    assert _option_value(commands[1].args, "--PatchMatchStereo.geom_consistency") == "1"
    assert _option_value(commands[2].args, "--input_type") == "geometric"


def test_dense_photometric_mode_uses_photometric_fusion(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config.advanced.sfm.dense.enabled = True

    commands = build_dense_commands(config=config, workspace_path=tmp_path / "undistorted")

    assert [command.stage for command in commands[:2]] == [
        "sfm.dense.patch_match",
        "sfm.dense.fusion",
    ]
    assert _option_value(commands[0].args, "--PatchMatchStereo.geom_consistency") == "0"
    assert _option_value(commands[1].args, "--input_type") == "photometric"


def test_dense_mesh_defaults_to_delaunay(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config.advanced.sfm.dense.enabled = True
    config.advanced.sfm.dense.mesh.enabled = True

    commands = build_dense_commands(config=config, workspace_path=tmp_path / "undistorted")

    mesh_command = commands[-1]
    assert mesh_command.command_name == "delaunay_mesher"
    assert mesh_command.stage == "sfm.mesh"
    assert _option_value(mesh_command.args, "--input_path") == str(tmp_path / "undistorted")
    assert _option_value(mesh_command.args, "--input_type") == "dense"
    assert _option_value(mesh_command.args, "--output_path") == str(
        tmp_path / "undistorted" / "meshed-delaunay.ply"
    )


def test_dense_mesh_poisson_method_uses_fused_cloud(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config.advanced.sfm.dense.enabled = True
    config.advanced.sfm.dense.mesh.enabled = True
    config.advanced.sfm.dense.mesh.method = "poisson"

    commands = build_dense_commands(config=config, workspace_path=tmp_path / "undistorted")

    mesh_command = commands[-1]
    assert mesh_command.command_name == "poisson_mesher"
    assert mesh_command.stage == "sfm.mesh"
    assert _option_value(mesh_command.args, "--input_path") == str(
        tmp_path / "undistorted" / "fused.ply"
    )
    assert _option_value(mesh_command.args, "--output_path") == str(
        tmp_path / "undistorted" / "meshed-poisson.ply"
    )
    assert _option_value(mesh_command.args, "--PoissonMeshing.depth") == "13"
