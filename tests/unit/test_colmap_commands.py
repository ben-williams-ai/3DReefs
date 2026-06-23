"""Tests for COLMAP command construction."""

from __future__ import annotations

from pathlib import Path

from reefs.colmap.commands import (
    build_feature_extractor,
    build_matcher_commands,
    build_reconstruction_command,
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


def test_default_matcher_commands_are_ordered(tmp_path: Path) -> None:
    config = _config(tmp_path)

    commands = build_matcher_commands(
        config=config,
        database_path=tmp_path / "database.db",
        vocab_tree_path=tmp_path / "vocab.bin",
    )

    assert command_names(commands) == ["sequential_matcher", "vocab_tree_matcher"]


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
