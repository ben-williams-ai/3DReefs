"""Compatibility imports for ablation holdout helpers."""

from reefs.eval.holdout import (
    HoldoutSelection,
    _image_set_hash,
    build_eval_dataset,
    load_or_create_holdout,
    select_holdout,
    test_every_for_count,
)

__all__ = [
    "HoldoutSelection",
    "_image_set_hash",
    "build_eval_dataset",
    "load_or_create_holdout",
    "select_holdout",
    "test_every_for_count",
]
