"""LichtFeld Studio command construction helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LfsCommand:
    """LichtFeld Studio command for one patch."""

    patch_id: str
    args: list[str]
    dataset_dir: Path
    output_dir: Path

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable command record."""
        return {
            "patch_id": self.patch_id,
            "args": self.args,
            "dataset_dir": str(self.dataset_dir),
            "output_dir": str(self.output_dir),
        }


def build_lfs_train_command(
    *,
    lfs_bin: str,
    patch_id: str,
    dataset_dir: Path,
    output_dir: Path,
    num_iters: int,
    num_splats_per_patch: int,
    strategy: str,
    headless: bool,
    max_width: int | None,
    lfs_config: Path | None,
    eval_enabled: bool = False,
    test_every: int | None = None,
) -> LfsCommand:
    """Build the LFS training command evidenced by the old pipeline."""
    args = [lfs_bin, "-d", str(dataset_dir), "-o", str(output_dir)]
    if lfs_config is not None:
        args.extend(["--config", str(lfs_config)])
    if headless:
        args.append("--headless")
    if max_width is not None:
        args.extend(["--max-width", str(max_width)])
    if eval_enabled:
        args.append("--eval")
        args.append("--no-save-eval-images")
    if test_every is not None:
        args.extend(["--test-every", str(test_every)])
    args.extend(["-i", str(num_iters)])
    args.extend(["--max-cap", str(num_splats_per_patch)])
    args.extend(["--strategy", strategy])
    return LfsCommand(patch_id=patch_id, args=args, dataset_dir=dataset_dir, output_dir=output_dir)


def write_lfs_eval_config(
    *,
    path: Path,
    base_config: Path | None,
    eval_steps: list[int],
    save_steps: list[int],
    headless: bool,
    eval_enabled: bool = True,
    save_eval_images: bool = False,
) -> Path:
    """Write an LFS JSON config that makes eval/save cadence explicit."""
    if base_config is None:
        raise ValueError("Explicit LFS eval cadence requires advanced.splat.train.lfs_config")
    data = json.loads(base_config.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"LFS config must contain a JSON object: {base_config}")
    data.update(
        {
            "eval_steps": eval_steps,
            "save_steps": save_steps,
            "enable_eval": eval_enabled,
            "enable_save_eval_images": save_eval_images,
            "headless": headless,
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return path
