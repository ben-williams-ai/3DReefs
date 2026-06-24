#!/usr/bin/env python3
"""Thin entrypoint for the 3DReefs ablation sweep runner."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from reefs.experiments.ablations.runner import main


if __name__ == "__main__":
    raise SystemExit(main())
