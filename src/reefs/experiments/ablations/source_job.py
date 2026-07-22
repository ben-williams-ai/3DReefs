"""Run one reusable Stage 2 SfM source preparation job."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from reefs.experiments.ablations.config import load_ablation_config
from reefs.experiments.ablations.grid import select_even_patch_ids
from reefs.experiments.ablations.source_bundle import validate_and_write_source_bundle
from reefs.eval.holdout import load_or_create_holdout
from reefs.patches.artefacts import read_image_names_text


def build_source_command(
    *,
    repo_root: Path,
    ablation_config: Path,
    pipeline_config: Path,
    project_dir: Path,
    dataset: str,
    run_id: str,
) -> list[str]:
    """Build the fixed 1024 SIFT-global source command."""
    config = load_ablation_config(ablation_config, repo_root=repo_root)
    variant_name = "sfm_1024_sift_global"
    variants = [variant for variant in config.sfm_variants if variant.name == variant_name]
    if len(variants) != 1:
        raise ValueError(f"expected exactly one {variant_name} variant")
    if dataset not in {item.name for item in config.datasets}:
        raise ValueError(f"unknown Stage 2 source dataset: {dataset}")
    overrides = {
        **variants[0].overrides,
        "advanced.sfm.feature_extraction.type": "SIFT",
        "advanced.sfm.feature_extraction.max_image_size": 1024,
        "advanced.sfm.reconstruction.backend": "global",
        "advanced.sfm.undistortion.additional_max_image_sizes": [2048],
        "advanced.eval.target_image_source": "full_resolution_undistorted",
        "advanced.eval.full_resolution_undistorted_images_dir": None,
        "advanced.sfm.preflight.colmap_target_version": "9c23f694",
    }
    command = [
        sys.executable,
        str(repo_root / "main.py"),
        "--config",
        str(pipeline_config),
        "--project-dir",
        str(project_dir),
        "--steps",
        "sfm",
        "--resume-policy",
        "overwrite",
        "--run-id",
        run_id,
    ]
    for key, value in overrides.items():
        command.extend([f"--{key}", _override_value(value)])
    return command


def build_undistortion_recovery_command(
    *,
    repo_root: Path,
    ablation_config: Path,
    pipeline_config: Path,
    project_dir: Path,
    dataset: str,
    run_id: str,
) -> list[str]:
    """Build a source command that reruns undistortion and nothing upstream."""
    command = build_source_command(
        repo_root=repo_root,
        ablation_config=ablation_config,
        pipeline_config=pipeline_config,
        project_dir=project_dir,
        dataset=dataset,
        run_id=run_id,
    )
    command[command.index("--steps") + 1] = "sfm.undistort"
    return command


def run_source_job(
    *,
    repo_root: Path,
    ablation_config: Path,
    pipeline_config: Path,
    project_dir: Path,
    dataset: str,
    run_id: str,
    git_commit: str,
    git_ref: str,
    image_name: str,
    image_digest: str,
    recover_undistortion_only: bool = False,
) -> None:
    """Run SfM once, validate all undistortions, and write source metadata."""
    command_builder = build_undistortion_recovery_command if recover_undistortion_only else build_source_command
    command = command_builder(
        repo_root=repo_root,
        ablation_config=ablation_config,
        pipeline_config=pipeline_config,
        project_dir=project_dir,
        dataset=dataset,
        run_id=run_id,
    )
    subprocess.run(command, cwd=repo_root, check=True)
    _write_canonical_patch_layouts(
        command=command,
        repo_root=repo_root,
        run_dir=project_dir / "runs" / run_id,
    )
    validate_and_write_source_bundle(
        run_dir=project_dir / "runs" / run_id,
        dataset=dataset,
        source_id=run_id,
        metadata={
            "git_commit": git_commit,
            "git_ref": git_ref,
            "git_ref_verified_pushed": True,
            "image_name": image_name,
            "image_digest": image_digest,
            "colmap_commit": "9c23f6942fe69962e06030905e77067c8673382f",
            "lfs_commit": "6d591a34",
        },
    )


def _write_canonical_patch_layouts(*, command: list[str], repo_root: Path, run_dir: Path) -> None:
    """Generate patch membership and holdouts once from the fixed 1024 tree."""
    steps_index = command.index("--steps") + 1
    for patch_size in [200, 400, 800]:
        patch_command = list(command)
        patch_command[steps_index] = "splat.patch"
        patch_command.extend(["--advanced.splat.patching.max_cameras", str(patch_size)])
        subprocess.run(patch_command, cwd=repo_root, check=True)
        patches = run_dir / "splat" / "patches"
        usable_ids = [
            path.name
            for path in patches.iterdir()
            if path.is_dir() and _patch_has_registered_internal_images(path)
        ]
        selected_ids = select_even_patch_ids(usable_ids, 10)
        layout = run_dir / "stage2_patch_layouts" / f"patch{patch_size}"
        if layout.exists():
            shutil.rmtree(layout)
        layout.mkdir(parents=True, exist_ok=True)
        (layout / "selection.json").write_text(
            json.dumps({"patch_size": patch_size, "selected_patch_ids": selected_ids}, indent=2) + "\n",
            encoding="utf-8",
        )
        for patch_id in selected_ids:
            source_patch = patches / patch_id
            target_patch = layout / "patches" / patch_id
            target_patch.mkdir(parents=True)
            shutil.copy2(source_patch / "patch_metadata.json", target_patch / "patch_metadata.json")
            load_or_create_holdout(
                patch_dir=source_patch,
                canonical_path=target_patch / "holdout.json",
                holdout_fraction=0.1,
            )
    shutil.rmtree(run_dir / "splat")


def _patch_has_registered_internal_images(patch_dir: Path) -> bool:
    """Return whether a patch can produce a canonical internal holdout."""
    metadata = json.loads((patch_dir / "patch_metadata.json").read_text(encoding="utf-8"))
    selected = [str(name) for name in metadata["selected_images"]]
    internal = set(selected[: int(metadata["selected_internal_count"])])
    registered = set(read_image_names_text(patch_dir / "sparse" / "0" / "images.txt"))
    return bool(internal & registered)


def _override_value(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return "[" + ",".join(str(item) for item in value) + "]"
    return str(value)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for a source worker."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--ablation-config", type=Path, required=True)
    parser.add_argument("--pipeline-config", type=Path, required=True)
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--git-commit", required=True)
    parser.add_argument("--git-ref", required=True)
    parser.add_argument("--image-name", required=True)
    parser.add_argument("--image-digest", required=True)
    parser.add_argument("--recover-undistortion-only", action="store_true")
    args = parser.parse_args(argv)
    run_source_job(
        repo_root=args.repo_root,
        ablation_config=args.ablation_config,
        pipeline_config=args.pipeline_config,
        project_dir=args.project_dir,
        dataset=args.dataset,
        run_id=args.run_id,
        git_commit=args.git_commit,
        git_ref=args.git_ref,
        image_name=args.image_name,
        image_digest=args.image_digest,
        recover_undistortion_only=args.recover_undistortion_only,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
