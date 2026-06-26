"""Bounded external tool validation."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from time import perf_counter


@dataclass(frozen=True)
class ToolValidation:
    """External tool validation result."""

    tool_name: str
    configured_path: str
    detected_version: str | None
    target_version: str | None
    capabilities_checked: list[str]
    status: str
    message: str
    duration_seconds: float

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable result."""
        return {
            "tool_name": self.tool_name,
            "configured_path": self.configured_path,
            "detected_version": self.detected_version,
            "target_version": self.target_version,
            "capabilities_checked": self.capabilities_checked,
            "status": self.status,
            "message": self.message,
            "duration_seconds": self.duration_seconds,
        }


def run_tool_command(binary: str, args: list[str], timeout: float = 5.0) -> subprocess.CompletedProcess[str]:
    """Run a bounded tool command."""
    return subprocess.run(
        [binary, *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(part for part in [result.stdout, result.stderr] if part)


def validate_tool(
    *, tool_name: str, binary: str, target_version: str | None, version_args: list[str] | None = None
) -> ToolValidation:
    """Validate one external tool with version/help commands only."""
    start = perf_counter()
    capabilities = ["exists"]
    resolved = shutil.which(binary) if "/" not in binary else binary
    if resolved is None:
        return ToolValidation(
            tool_name=tool_name,
            configured_path=binary,
            detected_version=None,
            target_version=target_version,
            capabilities_checked=capabilities,
            status="failed",
            message=f"{tool_name} binary not found: {binary}",
            duration_seconds=round(perf_counter() - start, 6),
        )

    detected = ""
    try:
        capabilities.append("version")
        version_result = run_tool_command(binary, version_args or ["--version"])
        detected = _combined_output(version_result).strip()
        if version_result.returncode not in {0, 1}:
            return ToolValidation(
                tool_name=tool_name,
                configured_path=binary,
                detected_version=detected or None,
                target_version=target_version,
                capabilities_checked=capabilities,
                status="failed",
                message=f"{tool_name} version command failed",
                duration_seconds=round(perf_counter() - start, 6),
            )
        if target_version and target_version not in detected:
            return ToolValidation(
                tool_name=tool_name,
                configured_path=binary,
                detected_version=detected,
                target_version=target_version,
                capabilities_checked=capabilities,
                status="failed",
                message=f"{tool_name} version does not include target {target_version}",
                duration_seconds=round(perf_counter() - start, 6),
            )
        capabilities.append("help")
        help_result = run_tool_command(binary, ["--help"])
        if help_result.returncode not in {0, 1}:
            return ToolValidation(
                tool_name=tool_name,
                configured_path=binary,
                detected_version=detected,
                target_version=target_version,
                capabilities_checked=capabilities,
                status="failed",
                message=f"{tool_name} help command failed",
                duration_seconds=round(perf_counter() - start, 6),
            )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return ToolValidation(
            tool_name=tool_name,
            configured_path=binary,
            detected_version=detected or None,
            target_version=target_version,
            capabilities_checked=capabilities,
            status="failed",
            message=f"{tool_name} validation failed: {exc}",
            duration_seconds=round(perf_counter() - start, 6),
        )

    return ToolValidation(
        tool_name=tool_name,
        configured_path=binary,
        detected_version=detected,
        target_version=target_version,
        capabilities_checked=capabilities,
        status="passed",
        message=f"{tool_name} validation passed",
        duration_seconds=round(perf_counter() - start, 6),
    )


def validate_splat_transform(binary: str, *, require_sog: bool) -> ToolValidation:
    """Validate splat-transform and the formats required by SOG export."""
    start = perf_counter()
    capabilities = ["exists"]
    resolved = shutil.which(binary) if "/" not in binary else binary
    if resolved is None:
        return ToolValidation(
            tool_name="splat-transform",
            configured_path=binary,
            detected_version=None,
            target_version=None,
            capabilities_checked=capabilities,
            status="failed",
            message=f"splat-transform binary not found: {binary}",
            duration_seconds=round(perf_counter() - start, 6),
        )
    try:
        capabilities.append("version")
        version_result = run_tool_command(binary, ["--version"])
        detected = _combined_output(version_result).strip()
        capabilities.append("help")
        help_result = run_tool_command(binary, ["--help"])
        help_text = _combined_output(help_result)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return ToolValidation(
            tool_name="splat-transform",
            configured_path=binary,
            detected_version=None,
            target_version=None,
            capabilities_checked=capabilities,
            status="failed",
            message=f"splat-transform validation failed: {exc}",
            duration_seconds=round(perf_counter() - start, 6),
        )
    required_tokens = [".ply"]
    if require_sog:
        required_tokens.append(".sog")
    missing = [token for token in required_tokens if token not in help_text]
    if missing:
        return ToolValidation(
            tool_name="splat-transform",
            configured_path=binary,
            detected_version=detected,
            target_version=None,
            capabilities_checked=[*capabilities, "formats"],
            status="failed",
            message="splat-transform help is missing required capabilities: " + ", ".join(missing),
            duration_seconds=round(perf_counter() - start, 6),
        )
    return ToolValidation(
        tool_name="splat-transform",
        configured_path=binary,
        detected_version=detected,
        target_version=None,
        capabilities_checked=[*capabilities, "ply", "sog" if require_sog else "ply"],
        status="passed",
        message="splat-transform validation passed",
        duration_seconds=round(perf_counter() - start, 6),
    )
