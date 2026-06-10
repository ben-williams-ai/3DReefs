"""Thin entrypoint for the 3DReefs pipeline CLI."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from reefs.cli import app


if __name__ == "__main__":
    app()
