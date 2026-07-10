"""Validation and inventory helpers for reusable Stage 2 SfM source bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

import yaml

from reefs.patches.artefacts import detect_sparse_model_files, ensure_text_sparse_model


WORKSPACES = {
    "1024": "undistorted",
    "2048": "undistorted_2048",
    "full": "undistorted_full_resolution",
}


def validate_and_write_source_bundle(
    *,
    run_dir: Path,
    dataset: str,
    source_id: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a complete Stage 2 source and write its manifest/checksums."""
    sfm_dir = run_dir / "sfm"
    if not sfm_dir.is_dir():
        raise ValueError(f"missing Stage 2 source SfM directory: {sfm_dir}")
    if not (sfm_dir / "database.db").is_file():
        raise ValueError(f"missing Stage 2 source database: {sfm_dir / 'database.db'}")
    detect_sparse_model_files(sfm_dir / "selected_sparse")
    sparse_models = sorted(path for path in (sfm_dir / "sparse").iterdir() if path.is_dir())
    if not sparse_models:
        raise ValueError(f"missing original Stage 2 reconstruction models: {sfm_dir / 'sparse'}")
    for model in sparse_models:
        detect_sparse_model_files(model)

    workspaces: dict[str, dict[str, Any]] = {}
    reference: dict[str, Any] | None = None
    registered_image_names: list[str] = []
    with tempfile.TemporaryDirectory(prefix="3dreefs-stage2-source-") as temporary:
        temporary_root = Path(temporary)
        for resolution, relative in WORKSPACES.items():
            workspace = sfm_dir / relative
            images_dir = workspace / "images"
            sparse_dir = workspace / "sparse"
            if not images_dir.is_dir():
                raise ValueError(f"missing Stage 2 source image tree: {images_dir}")
            detected = detect_sparse_model_files(sparse_dir)
            text_sparse = ensure_text_sparse_model(sparse_dir, temporary_root / resolution)
            signature = _sparse_signature(text_sparse)
            image_files = sorted(
                path.relative_to(images_dir).as_posix()
                for path in images_dir.rglob("*")
                if path.is_file()
            )
            registered_names = signature.pop("registered_names")
            if not registered_image_names:
                registered_image_names = registered_names
            missing = sorted(set(registered_names) - set(image_files))
            extra = sorted(set(image_files) - set(registered_names))
            if missing or extra:
                raise ValueError(
                    f"{resolution} source image tree differs from its sparse model: "
                    f"missing={len(missing)}, extra={len(extra)}; "
                    + ", ".join((missing + extra)[:5])
                )
            comparable = {
                "registered_names_hash": signature["registered_names_hash"],
                "poses_hash": signature["poses_hash"],
                "points3d_hash": signature["points3d_hash"],
                "registered_image_count": signature["registered_image_count"],
                "sparse_point_count": signature["sparse_point_count"],
            }
            if reference is None:
                reference = comparable
            elif comparable != reference:
                differing = sorted(key for key in comparable if comparable[key] != reference[key])
                raise ValueError(
                    f"Stage 2 source geometry differs for {resolution}: " + ", ".join(differing)
                )
            workspaces[resolution] = {
                "path": str(workspace.relative_to(run_dir)),
                "images_path": str(images_dir.relative_to(run_dir)),
                "sparse_path": str(sparse_dir.relative_to(run_dir)),
                "sparse_format": detected.format,
                "image_file_count": len(image_files),
                "image_files_hash": _hash_lines(image_files),
                **signature,
            }

    inventory = _source_inventory(run_dir)
    checksums_path = run_dir / "checksums.sha256"
    checksums_path.write_text(
        "".join(f"{item['sha256']}  {item['path']}\n" for item in inventory),
        encoding="utf-8",
    )
    manifest = {
        "status": "validated",
        "dataset": dataset,
        "source_id": source_id,
        "source_variant": "sfm_1024_sift_global",
        "registered_image_names": registered_image_names,
        "workspaces": workspaces,
        "inventory_file_count": len(inventory),
        "inventory_size_bytes": sum(int(item["size_bytes"]) for item in inventory),
        "checksums_path": checksums_path.name,
        "effective_config": _read_yaml_if_present(run_dir / "effective_config.yml"),
        "run_manifest": _read_json_if_present(run_dir / "run_manifest.json"),
        **(metadata or {}),
    }
    (run_dir / "source_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def verify_checksums(run_dir: Path, *, included_prefixes: list[str] | None = None) -> None:
    """Verify every object listed in a source bundle checksum file."""
    checksums = run_dir / "checksums.sha256"
    if not checksums.is_file():
        raise ValueError(f"missing source checksum file: {checksums}")
    verified = 0
    for line in checksums.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split(maxsplit=1)
        relative = relative.strip()
        if included_prefixes and not any(
            relative == prefix.rstrip("/") or relative.startswith(prefix.rstrip("/") + "/")
            for prefix in included_prefixes
        ):
            continue
        path = run_dir / relative.strip()
        if not path.is_file():
            raise ValueError(f"source checksum object is missing: {relative}")
        actual = _sha256_file(path)
        if actual != expected:
            raise ValueError(f"source checksum mismatch for {relative}: {actual} != {expected}")
        verified += 1
    if verified == 0:
        raise ValueError("source checksum selection did not match any objects")


def _sparse_signature(model_dir: Path) -> dict[str, Any]:
    names: list[str] = []
    pose_rows: list[str] = []
    with (model_dir / "images.txt").open("r", encoding="utf-8", errors="replace") as handle:
        while True:
            header = handle.readline()
            if not header:
                break
            stripped = header.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = stripped.split(maxsplit=9)
            if len(parts) != 10:
                raise ValueError(f"invalid COLMAP image row under {model_dir}: {stripped[:120]}")
            handle.readline()
            name = parts[9]
            names.append(name)
            pose_rows.append(" ".join([parts[0], *parts[1:8], name]))

    points = hashlib.sha256()
    point_count = 0
    with (model_dir / "points3D.txt").open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = stripped.split()
            if len(parts) < 4:
                raise ValueError(f"invalid COLMAP point row under {model_dir}: {stripped[:120]}")
            points.update(" ".join(parts[:4]).encode("utf-8"))
            points.update(b"\n")
            point_count += 1

    camera_dimensions: list[dict[str, Any]] = []
    with (model_dir / "cameras.txt").open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = stripped.split()
            camera_dimensions.append(
                {
                    "camera_id": int(parts[0]),
                    "model": parts[1],
                    "width": int(parts[2]),
                    "height": int(parts[3]),
                    "params": [float(value) for value in parts[4:]],
                }
            )
    ordered_names = sorted(names)
    return {
        "registered_names": ordered_names,
        "registered_names_hash": _hash_lines(ordered_names),
        "poses_hash": _hash_lines(sorted(pose_rows)),
        "points3d_hash": points.hexdigest(),
        "registered_image_count": len(names),
        "sparse_point_count": point_count,
        "camera_count": len(camera_dimensions),
        "camera_dimensions": camera_dimensions,
    }


def _source_inventory(run_dir: Path) -> list[dict[str, Any]]:
    excluded = {
        "checksums.sha256",
        "source_manifest.json",
        # The host sampler keeps appending until the worker exits.
        "resource_samples.csv",
        "resource_summary.json",
        "source_complete.json",
        "source_upload_pending.json",
    }
    return [
        {
            "path": path.relative_to(run_dir).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
        }
        for path in sorted(run_dir.rglob("*"))
        if path.is_file() and path.relative_to(run_dir).as_posix() not in excluded
    ]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_lines(lines: list[str]) -> str:
    digest = hashlib.sha256()
    for line in lines:
        digest.update(line.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _read_json_if_present(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else None


def _read_yaml_if_present(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else None


def main(argv: list[str] | None = None) -> int:
    """Validate a source run and write its immutable inventory metadata."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--git-commit")
    parser.add_argument("--image-name")
    args = parser.parse_args(argv)
    validate_and_write_source_bundle(
        run_dir=args.run_dir,
        dataset=args.dataset,
        source_id=args.source_id,
        metadata={"git_commit": args.git_commit, "image_name": args.image_name},
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
