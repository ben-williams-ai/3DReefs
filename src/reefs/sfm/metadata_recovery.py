"""Lossless image-metadata recovery for COLMAP undistortion."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class MetadataRecoveryResult:
    """Verified metadata-stripped image tree and its audit artefacts."""

    source_root: str
    recovered_root: str
    image_count: int
    staging_method: str
    exiftool_version: str
    source_hash_manifest: str
    recovered_hash_manifest: str

    def as_dict(self) -> dict[str, object]:
        """Return JSON-serialisable recovery metadata."""
        return asdict(self)


def prepare_metadata_stripped_images(
    *,
    source_root: Path,
    recovered_root: Path,
    audit_root: Path,
    exiftool_bin: str = "exiftool",
) -> MetadataRecoveryResult:
    """Strip metadata in an isolated tree and prove image payloads are unchanged."""
    if recovered_root.exists():
        shutil.rmtree(recovered_root)
    audit_root.mkdir(parents=True, exist_ok=True)
    try:
        source_hashes = image_data_hashes(source_root, exiftool_bin=exiftool_bin)
        staging_method = stage_image_tree(source_root, recovered_root)
        _run_exiftool(
            [exiftool_bin, "-overwrite_original", "-all=", "-r", str(recovered_root)]
        )
        recovered_hashes = image_data_hashes(recovered_root, exiftool_bin=exiftool_bin)
        if source_hashes != recovered_hashes:
            missing = sorted(set(source_hashes) - set(recovered_hashes))
            extra = sorted(set(recovered_hashes) - set(source_hashes))
            changed = sorted(
                path
                for path in set(source_hashes).intersection(recovered_hashes)
                if source_hashes[path] != recovered_hashes[path]
            )
            raise ValueError(
                "Metadata recovery changed image payloads: "
                f"missing={len(missing)}, extra={len(extra)}, changed={len(changed)}"
            )
        source_manifest = audit_root / "image_data_hashes_before.sha256"
        recovered_manifest = audit_root / "image_data_hashes_after.sha256"
        _write_hash_manifest(source_manifest, source_hashes)
        _write_hash_manifest(recovered_manifest, recovered_hashes)
        version = _run_exiftool([exiftool_bin, "-ver"]).stdout.strip()
        return MetadataRecoveryResult(
            source_root=str(source_root),
            recovered_root=str(recovered_root),
            image_count=len(source_hashes),
            staging_method=staging_method,
            exiftool_version=version,
            source_hash_manifest=str(source_manifest),
            recovered_hash_manifest=str(recovered_manifest),
        )
    except Exception:
        if recovered_root.exists():
            shutil.rmtree(recovered_root)
        raise


def stage_image_tree(source_root: Path, recovered_root: Path) -> str:
    """Stage images with hardlinks, falling back to independent copies."""
    if not source_root.is_dir():
        raise ValueError(f"Metadata recovery source is not a directory: {source_root}")
    try:
        shutil.copytree(source_root, recovered_root, copy_function=os.link)
        return "hardlink"
    except OSError:
        if recovered_root.exists():
            shutil.rmtree(recovered_root)
        shutil.copytree(source_root, recovered_root)
        return "copy"


def image_data_hashes(root: Path, *, exiftool_bin: str = "exiftool") -> dict[str, str]:
    """Return ExifTool ImageDataHash values keyed by relative image path."""
    root = root.resolve()
    result = _run_exiftool([exiftool_bin, "-json", "-r", "-ImageDataHash", str(root)])
    records = json.loads(result.stdout)
    hashes: dict[str, str] = {}
    for record in records:
        source = Path(str(record.get("SourceFile", ""))).resolve()
        try:
            relative = source.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError(f"ExifTool returned a path outside the image root: {source}") from exc
        value = str(record.get("ImageDataHash", "")).strip()
        if not relative or not value:
            raise ValueError(f"ExifTool returned no ImageDataHash for {source}")
        if relative in hashes:
            raise ValueError(f"ExifTool returned duplicate image path: {relative}")
        hashes[relative] = value
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }
    if not hashes or set(hashes) != actual:
        raise ValueError(
            "ExifTool ImageDataHash inventory differs from the image tree: "
            f"files={len(actual)}, hashes={len(hashes)}"
        )
    return hashes


def _run_exiftool(args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"ExifTool metadata recovery command failed: {' '.join(args)}") from exc


def _write_hash_manifest(path: Path, hashes: dict[str, str]) -> None:
    path.write_text(
        "".join(f"{value}  {relative}\n" for relative, value in sorted(hashes.items())),
        encoding="utf-8",
    )
