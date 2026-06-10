"""YAML and JSON helpers for run records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


def read_yaml(path: Path) -> dict[str, Any]:
    """Read a YAML mapping from disk."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Config file does not exist: {path}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"Config file is not valid YAML: {path}") from exc

    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML file must contain a mapping at the top level: {path}")
    return data


def write_yaml(path: Path, data: Any) -> None:
    """Write YAML with stable key ordering disabled for readability."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )


def read_json(path: Path) -> Any:
    """Read JSON from disk."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"JSON file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON file is not valid: {path}") from exc


def write_json(path: Path, data: Any) -> None:
    """Write indented JSON to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")
