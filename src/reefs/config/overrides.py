"""CLI override parsing and application."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from pydantic import ValidationError

from reefs.config.models import PipelineConfig


def parse_unknown_overrides(args: list[str]) -> list[dict[str, object]]:
    """Parse Typer/Click unknown args as dotted config overrides.

    Args:
        args: Remaining command-line args, usually from ``ctx.args``.

    Returns:
        Override records with raw string values.

    Raises:
        ValueError: If an arg is not a ``--dotted.path value`` pair.
    """
    overrides: list[dict[str, object]] = []
    index = 0
    while index < len(args):
        key_arg = args[index]
        if not key_arg.startswith("--") or key_arg == "--":
            raise ValueError(f"Unexpected override argument: {key_arg}")
        if index + 1 >= len(args):
            raise ValueError(f"Override {key_arg} requires a value")
        key = key_arg[2:]
        raw_value = args[index + 1]
        if not key or "." not in key:
            raise ValueError(f"Override key must be a dotted config path: {key_arg}")
        overrides.append(
            {
                "key": key,
                "raw_value": raw_value,
                "parsed_value": raw_value,
                "source": "cli",
            }
        )
        index += 2
    return overrides


def _coerce_value(raw_value: str) -> Any:
    lowered = raw_value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"none", "null"}:
        return None
    try:
        return int(raw_value)
    except ValueError:
        pass
    try:
        return float(raw_value)
    except ValueError:
        return raw_value


def _set_dotted_value(data: dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = dotted_key.split(".")
    cursor: dict[str, Any] = data
    for part in parts[:-1]:
        next_value = cursor.get(part)
        if not isinstance(next_value, dict):
            raise ValueError(f"Unknown override key: {dotted_key}")
        cursor = next_value
    if parts[-1] not in cursor:
        raise ValueError(f"Unknown override key: {dotted_key}")
    cursor[parts[-1]] = value


def apply_overrides(
    config: PipelineConfig, overrides: list[dict[str, object]]
) -> tuple[PipelineConfig, list[dict[str, object]]]:
    """Apply override records to a typed config and revalidate."""
    data = deepcopy(config.model_dump(mode="python"))
    accepted: list[dict[str, object]] = []
    for override in overrides:
        key = str(override["key"])
        parsed_value = _coerce_value(str(override["raw_value"]))
        _set_dotted_value(data, key, parsed_value)
        accepted.append({**override, "parsed_value": parsed_value})
    try:
        return PipelineConfig.model_validate(data), accepted
    except ValidationError as exc:
        raise ValueError(f"Invalid override value: {exc}") from exc
