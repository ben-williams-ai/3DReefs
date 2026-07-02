"""Write cross-camera pair previews for configured datasets."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from reefs.config.loader import load_config
from reefs.io.paths import derive_project_paths
from reefs.preflight.images import detect_image_layout
from reefs.sfm.cross_camera_pairs import generate_cross_camera_pairs, write_pair_preview


DEFAULT_DATASETS = {
    "dataset1": Path("configs/datasets/dataset_01.yml"),
    "dataset2": Path("configs/datasets/dataset_02.yml"),
    "dataset3": Path("configs/datasets/dataset_03.yml"),
    "dataset4": Path("configs/datasets/dataset_04.yml"),
}


def main() -> int:
    """Generate preview files under scratch/cross_camera_pairs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=Path("scratch/cross_camera_pairs"))
    parser.add_argument("--index-window", type=int, default=1)
    parser.add_argument("--ordering", choices=["exif_timestamp", "filename"], default=None)
    parser.add_argument("--preview-count", type=int, default=20)
    args = parser.parse_args()

    for name, config_path in DEFAULT_DATASETS.items():
        config = load_config(config_path)
        paths = derive_project_paths(config)
        layout = detect_image_layout(paths.raw_images)
        cross_config = config.advanced.sfm.matching.cross_camera_pairs
        result = generate_cross_camera_pairs(
            layout,
            index_window=args.index_window,
            ordering=args.ordering or cross_config.ordering,
        )
        dataset_dir = args.out_dir / name
        write_pair_preview(
            result,
            preview_path=dataset_dir / "pairs_preview.txt",
            summary_path=dataset_dir / "summary.json",
            preview_count=args.preview_count,
        )
        print(f"{name}: {len(result.pairs)} pair(s) -> {dataset_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
