"""Tests for lossless undistortion metadata recovery."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from reefs.sfm import metadata_recovery


def _completed(stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["exiftool"], returncode=0, stdout=stdout, stderr="")


def test_stage_image_tree_hardlinks_nested_paths_with_spaces(tmp_path: Path) -> None:
    source = tmp_path / "raw images"
    image = source / "camera one" / "image 01.jpg"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"jpeg-data")
    recovered = tmp_path / "recovered images"

    method = metadata_recovery.stage_image_tree(source, recovered)

    staged = recovered / "camera one" / "image 01.jpg"
    assert method == "hardlink"
    assert staged.read_bytes() == b"jpeg-data"
    assert staged.stat().st_ino == image.stat().st_ino


def test_stage_image_tree_falls_back_to_copy(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "raw"
    source.mkdir()
    (source / "a.jpg").write_bytes(b"a")
    recovered = tmp_path / "recovered"
    real_copytree = metadata_recovery.shutil.copytree
    calls = 0

    def fake_copytree(src, dst, copy_function=None):
        nonlocal calls
        calls += 1
        if copy_function is os.link:
            Path(dst).mkdir()
            raise OSError("hardlinks unavailable")
        return real_copytree(src, dst) if copy_function is None else real_copytree(
            src, dst, copy_function=copy_function
        )

    monkeypatch.setattr(metadata_recovery.shutil, "copytree", fake_copytree)

    assert metadata_recovery.stage_image_tree(source, recovered) == "copy"
    assert calls == 2
    assert (recovered / "a.jpg").read_bytes() == b"a"
    assert (recovered / "a.jpg").stat().st_ino != (source / "a.jpg").stat().st_ino


def test_image_data_hashes_reads_complete_nested_inventory(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "raw images"
    first = root / "cam 1" / "a.jpg"
    second = root / "cam2" / "b.jpg"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_bytes(b"a")
    second.write_bytes(b"b")
    payload = json.dumps(
        [
            {"SourceFile": str(first), "ImageDataHash": "hash-a"},
            {"SourceFile": str(second), "ImageDataHash": "hash-b"},
        ]
    )
    monkeypatch.setattr(metadata_recovery, "_run_exiftool", lambda args: _completed(payload))

    assert metadata_recovery.image_data_hashes(root) == {
        "cam 1/a.jpg": "hash-a",
        "cam2/b.jpg": "hash-b",
    }


@pytest.mark.parametrize(
    "records",
    [
        [],
        [{"SourceFile": "a.jpg", "ImageDataHash": ""}],
        [{"SourceFile": "a.jpg", "ImageDataHash": "hash"}],
    ],
)
def test_image_data_hashes_rejects_incomplete_inventory(
    tmp_path: Path, monkeypatch, records: list[dict[str, str]]
) -> None:
    root = tmp_path / "raw"
    root.mkdir()
    (root / "a.jpg").write_bytes(b"a")
    normalised = [
        {**record, "SourceFile": str(root / record["SourceFile"])} for record in records
    ]
    if records and records[0]["ImageDataHash"]:
        (root / "extra.jpg").write_bytes(b"extra")
    monkeypatch.setattr(
        metadata_recovery,
        "_run_exiftool",
        lambda args: _completed(json.dumps(normalised)),
    )

    with pytest.raises(ValueError):
        metadata_recovery.image_data_hashes(root)


def test_prepare_metadata_stripped_images_preserves_source_and_writes_audit(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "raw"
    source.mkdir()
    original = source / "a.jpg"
    original.write_bytes(b"original-with-metadata")
    recovered = tmp_path / "recovered"
    audit = tmp_path / "audit"
    inventories = iter([{"a.jpg": "pixel-hash"}, {"a.jpg": "pixel-hash"}])
    monkeypatch.setattr(metadata_recovery, "image_data_hashes", lambda *args, **kwargs: next(inventories))

    def fake_exiftool(args: list[str]) -> subprocess.CompletedProcess[str]:
        if "-all=" in args:
            target = recovered / "a.jpg"
            target.unlink()
            target.write_bytes(b"stripped-metadata-same-pixels")
            return _completed()
        return _completed("13.40\n")

    monkeypatch.setattr(metadata_recovery, "_run_exiftool", fake_exiftool)

    result = metadata_recovery.prepare_metadata_stripped_images(
        source_root=source,
        recovered_root=recovered,
        audit_root=audit,
    )

    assert original.read_bytes() == b"original-with-metadata"
    assert result.image_count == 1
    assert result.staging_method == "hardlink"
    assert result.exiftool_version == "13.40"
    assert (audit / "image_data_hashes_before.sha256").read_text() == "pixel-hash  a.jpg\n"
    assert (audit / "image_data_hashes_after.sha256").read_text() == "pixel-hash  a.jpg\n"


def test_prepare_metadata_stripped_images_rejects_changed_payload_and_cleans_tree(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "raw"
    source.mkdir()
    (source / "a.jpg").write_bytes(b"a")
    recovered = tmp_path / "recovered"
    inventories = iter([{"a.jpg": "before"}, {"a.jpg": "after"}])
    monkeypatch.setattr(metadata_recovery, "image_data_hashes", lambda *args, **kwargs: next(inventories))
    monkeypatch.setattr(metadata_recovery, "_run_exiftool", lambda args: _completed())

    with pytest.raises(ValueError, match="changed image payloads"):
        metadata_recovery.prepare_metadata_stripped_images(
            source_root=source,
            recovered_root=recovered,
            audit_root=tmp_path / "audit",
        )

    assert not recovered.exists()


def test_prepare_metadata_stripped_images_cleans_tree_when_exiftool_fails(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "raw"
    source.mkdir()
    (source / "a.jpg").write_bytes(b"a")
    recovered = tmp_path / "recovered"
    monkeypatch.setattr(metadata_recovery, "image_data_hashes", lambda *args, **kwargs: {"a.jpg": "hash"})

    def fail(args: list[str]) -> subprocess.CompletedProcess[str]:
        raise RuntimeError("ExifTool failed")

    monkeypatch.setattr(metadata_recovery, "_run_exiftool", fail)

    with pytest.raises(RuntimeError, match="ExifTool failed"):
        metadata_recovery.prepare_metadata_stripped_images(
            source_root=source,
            recovered_root=recovered,
            audit_root=tmp_path / "audit",
        )

    assert not recovered.exists()


def test_run_exiftool_wraps_command_failure(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, ["exiftool"])

    monkeypatch.setattr(metadata_recovery.subprocess, "run", fail)

    with pytest.raises(RuntimeError, match="metadata recovery command failed"):
        metadata_recovery._run_exiftool(["exiftool", "-ver"])


@pytest.mark.skipif(shutil.which("exiftool") is None, reason="ExifTool is not installed")
def test_real_exiftool_strips_metadata_without_changing_image_data(tmp_path: Path) -> None:
    source = tmp_path / "raw"
    source.mkdir()
    image_path = source / "with metadata.jpg"
    image = Image.new("RGB", (16, 12), color=(10, 20, 30))
    exif = Image.Exif()
    exif[0x010E] = "metadata recovery fixture"
    image.save(image_path, format="JPEG", exif=exif)
    original_bytes = image_path.read_bytes()

    result = metadata_recovery.prepare_metadata_stripped_images(
        source_root=source,
        recovered_root=tmp_path / "recovered",
        audit_root=tmp_path / "audit",
    )

    assert result.image_count == 1
    assert image_path.read_bytes() == original_bytes
    assert Image.open(tmp_path / "recovered" / "with metadata.jpg").getexif() == {}
