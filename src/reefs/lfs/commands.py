"""LichtFeld Studio command construction helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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
    lfs_config: Path | None,
) -> LfsCommand:
    """Build the LFS training command evidenced by the old pipeline."""
    args = [lfs_bin, "-d", str(dataset_dir), "-o", str(output_dir)]
    if lfs_config is not None:
        args.extend(["--config", str(lfs_config)])
    if headless:
        args.append("--headless")
    args.extend(["-i", str(num_iters)])
    args.extend(["--max-cap", str(num_splats_per_patch)])
    args.extend(["--strategy", strategy])
    return LfsCommand(patch_id=patch_id, args=args, dataset_dir=dataset_dir, output_dir=output_dir)
