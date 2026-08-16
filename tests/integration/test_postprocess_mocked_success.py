"""Mocked post-processing CLI flows."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

from click.testing import CliRunner

from reefs.cli import app
from reefs.io.yaml_json import write_json
from tests.conftest import write_config, write_test_jpeg, write_undistorted_sfm_fixture


def _fake_splat_transform(path: Path, *, fail_sog: bool = False) -> Path:
    path.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$1\" == \"--version\" ]]; then echo 'splat-transform v1.10.2'; exit 0; fi\n"
        "if [[ \"$1\" == \"--help\" ]]; then echo '.ply .sog --overwrite --filter-nan'; exit 0; fi\n"
        "out=\"${@: -1}\"\n"
        "if [[ \"$out\" == *.sog && \"" + ("1" if fail_sog else "0") + "\" == \"1\" ]]; then exit 9; fi\n"
        "in=''\n"
        "for arg in \"$@\"; do if [[ \"$arg\" == *.ply && -z \"$in\" ]]; then in=\"$arg\"; fi; done\n"
        "mkdir -p \"$(dirname \"$out\")\"\n"
        "if [[ -n \"$in\" ]]; then cp \"$in\" \"$out\"; else printf 'sog\\n' > \"$out\"; fi\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _install_fake_wildflow(monkeypatch) -> None:
    wildflow = types.ModuleType("wildflow")
    splat = types.ModuleType("wildflow.splat")

    def cleanup_splats(params: dict[str, object]) -> None:
        Path(str(params["output_file"])).write_text(
            Path(str(params["input_file"])).read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    def merge_ply_files(params: dict[str, object]) -> None:
        output = Path(str(params["output_file"]))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("".join(Path(path).read_text(encoding="utf-8") for path in params["input_files"]), encoding="utf-8")

    splat.cleanup_splats = cleanup_splats
    splat.merge_ply_files = merge_ply_files
    wildflow.splat = splat
    monkeypatch.setitem(sys.modules, "wildflow", wildflow)
    monkeypatch.setitem(sys.modules, "wildflow.splat", splat)


def _write_ply(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("ply\nformat ascii 1.0\nelement vertex 1\nend_header\n", encoding="utf-8")
    return path


def _prepare_trained_run(project: Path, run_id: str = "old", *, with_sfm: bool = True) -> Path:
    write_test_jpeg(project / "raw_images" / "image_0001.jpg")
    run_dir = project / "runs" / run_id
    run_dir.mkdir(parents=True)
    if with_sfm:
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


def test_splat_postprocess_creates_cleaned_merged_and_sog(tmp_path: Path, fake_tool_factory, monkeypatch) -> None:
    _install_fake_wildflow(monkeypatch)
    project = tmp_path / "project"
    run_dir = _prepare_trained_run(project)
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
            "splat.postprocess",
            "--resume-policy",
            "overwrite",
        ],
    )

    assert result.exit_code == 0, result.output
    assert (run_dir / "splat" / "patches" / "p000" / "splat" / "splat_finished_clean.ply").exists()
    assert (run_dir / "splat" / "merged" / "merged_splat.ply").exists()
    assert (run_dir / "splat" / "merged" / "merged_splat.sog").exists()
    manifest = json.loads((run_dir / "splat" / "postprocess" / "postprocess_manifest.json").read_text())
    assert manifest["status"] == "complete"
    assert manifest["cleanup"][0]["status"] == "complete"
    assert manifest["merge"]["included_count"] == 1
    assert manifest["sog"]["status"] == "complete"


def test_splat_postprocess_does_not_require_sfm_source(tmp_path: Path, fake_tool_factory, monkeypatch) -> None:
    _install_fake_wildflow(monkeypatch)
    project = tmp_path / "project"
    run_dir = _prepare_trained_run(project, with_sfm=False)
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
            "splat.postprocess",
            "--resume-policy",
            "overwrite",
        ],
    )

    assert result.exit_code == 0, result.output
    manifest = json.loads((run_dir / "run_manifest.json").read_text())
    assert manifest["splat_preflight"]["source"] is None


def test_sog_failure_preserves_merged_ply_and_marks_partial(tmp_path: Path, fake_tool_factory, monkeypatch) -> None:
    _install_fake_wildflow(monkeypatch)
    project = tmp_path / "project"
    run_dir = _prepare_trained_run(project)
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=fake_tool_factory("colmap", "COLMAP 4.0.4"),
        lfs_bin=fake_tool_factory("lfs", "LichtFeld Studio v0.5.2"),
        splat_transform_bin=_fake_splat_transform(tmp_path / "splat-transform", fail_sog=True),
    )

    result = CliRunner().invoke(
        app,
        [
            "--config",
            str(config),
            "--run-id",
            "old",
            "--steps",
            "splat.postprocess",
            "--resume-policy",
            "overwrite",
        ],
    )

    assert result.exit_code == 0, result.output
    assert (run_dir / "splat" / "merged" / "merged_splat.ply").exists()
    manifest = json.loads((run_dir / "splat" / "postprocess" / "postprocess_manifest.json").read_text())
    assert manifest["status"] == "partial"
    assert manifest["sog"]["status"] == "failed"
