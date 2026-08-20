"""Integration tests for post-processing resume and overwrite safeguards."""

from __future__ import annotations

import sys
import struct
import types
from pathlib import Path

from click.testing import CliRunner

from reefs.cli import app
from reefs.io.yaml_json import write_json
from tests.conftest import write_config, write_test_jpeg, write_undistorted_sfm_fixture


def _fake_splat_transform(path: Path) -> Path:
    path.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$1\" == \"--version\" ]]; then echo 'splat-transform v1.10.2'; exit 0; fi\n"
        "if [[ \"$1\" == \"--help\" ]]; then echo '.ply .sog --overwrite --filter-nan'; exit 0; fi\n"
        "out=\"${@: -1}\"\n"
        "in=''\n"
        "for arg in \"$@\"; do if [[ \"$arg\" == *.ply && -z \"$in\" ]]; then in=\"$arg\"; fi; done\n"
        "mkdir -p \"$(dirname \"$out\")\"\n"
        "cp \"$in\" \"$out\"\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _install_fake_wildflow(monkeypatch) -> None:
    wildflow = types.ModuleType("wildflow")
    splat = types.ModuleType("wildflow.splat")

    def cleanup_splats(params: dict[str, object]) -> None:
        Path(str(params["output_file"])).write_bytes(Path(str(params["input_file"])).read_bytes())

    splat.cleanup_splats = cleanup_splats
    splat.merge_ply_files = lambda _params: None
    wildflow.splat = splat
    monkeypatch.setitem(sys.modules, "wildflow", wildflow)
    monkeypatch.setitem(sys.modules, "wildflow.splat", splat)


def _write_ply(path: Path, text: str | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if text is not None:
        path.write_text(text, encoding="utf-8")
    else:
        path.write_bytes(
            b"ply\nformat binary_little_endian 1.0\nelement vertex 1\n"
            b"property float x\nproperty float y\nproperty float z\nend_header\n"
            + struct.pack("<fff", 0.5, 0.5, 0.5)
        )
    return path


def _prepare_run(project: Path) -> Path:
    write_test_jpeg(project / "raw_images" / "image_0001.jpg")
    run_dir = project / "runs" / "old"
    run_dir.mkdir(parents=True)
    write_undistorted_sfm_fixture(run_dir)
    patch = run_dir / "splat" / "patches" / "p000"
    write_json(
        patch / "patch_metadata.json",
        {
            "patch_id": "p000",
            "status": "valid",
            "bounds": {
                "min_x": 0,
                "max_x": 1,
                "min_y": 0,
                "max_y": 1,
                "min_z": 0,
                "max_z": 1,
                "buffer": 0.1,
            },
        },
    )
    source = _write_ply(patch / "splat" / "splat_finished.ply")
    write_json(
        patch / "splat" / "training_status.json",
        {
            "patch_id": "p000",
            "requested_iterations": 100,
            "completed_iterations": 100,
            "completion_ratio": 1.0,
            "output_file": str(source),
            "status": "complete",
        },
    )
    return run_dir


def test_postprocess_fail_policy_stops_before_overwriting_existing_outputs(tmp_path: Path, fake_tool_factory, monkeypatch) -> None:
    _install_fake_wildflow(monkeypatch)
    project = tmp_path / "project"
    run_dir = _prepare_run(project)
    existing = _write_ply(run_dir / "splat" / "patches" / "p000" / "splat" / "splat_finished_clean.ply", "keep\n")
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=fake_tool_factory("colmap", "COLMAP 4.0.4"),
        lfs_bin=fake_tool_factory("lfs", "LichtFeld Studio v0.5.2"),
        splat_transform_bin=_fake_splat_transform(tmp_path / "splat-transform"),
    )

    result = CliRunner().invoke(
        app,
        [
            "--config",
            str(config),
            "--run-id",
            "old",
            "--steps",
            "splat.cleanup",
            "--resume-policy",
            "fail",
        ],
    )

    assert result.exit_code != 0
    assert "Existing post-processing outputs require" in result.output
    assert existing.read_text(encoding="utf-8") == "keep\n"


def test_postprocess_overwrite_replaces_generated_outputs_only(tmp_path: Path, fake_tool_factory, monkeypatch) -> None:
    _install_fake_wildflow(monkeypatch)
    project = tmp_path / "project"
    run_dir = _prepare_run(project)
    source = run_dir / "splat" / "patches" / "p000" / "splat" / "splat_finished.ply"
    existing = _write_ply(run_dir / "splat" / "patches" / "p000" / "splat" / "splat_finished_clean.ply", "old\n")
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=fake_tool_factory("colmap", "COLMAP 4.0.4"),
        lfs_bin=fake_tool_factory("lfs", "LichtFeld Studio v0.5.2"),
        splat_transform_bin=_fake_splat_transform(tmp_path / "splat-transform"),
    )

    result = CliRunner().invoke(
        app,
        [
            "--config",
            str(config),
            "--run-id",
            "old",
            "--steps",
            "splat.cleanup",
            "--resume-policy",
            "overwrite",
        ],
    )

    assert result.exit_code == 0, result.output
    assert existing.exists()
    assert existing.read_bytes() == source.read_bytes()
    assert source.exists()
