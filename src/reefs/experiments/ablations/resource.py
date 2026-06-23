"""Per-job resource sampling."""

from __future__ import annotations

import csv
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from reefs.experiments.ablations.time_utils import utc_now


@dataclass(frozen=True)
class ResourceSummary:
    """Peak resource usage observed during one job."""

    peak_ram_mib: int | None
    peak_vram_mib: int | None
    samples: int

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable summary."""
        return {
            "peak_ram_mib": self.peak_ram_mib,
            "peak_vram_mib": self.peak_vram_mib,
            "samples": self.samples,
        }


class ResourceSampler:
    """Sample system RAM and GPU VRAM until stopped."""

    def __init__(self, output_csv: Path, *, interval_seconds: float = 30.0) -> None:
        self.output_csv = output_csv
        self.interval_seconds = interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._rows: list[dict[str, object]] = []

    def __enter__(self) -> "ResourceSampler":
        self.output_csv.parent.mkdir(parents=True, exist_ok=True)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.stop()

    def stop(self) -> ResourceSummary:
        """Stop sampling and return peak values."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(1.0, self.interval_seconds + 1.0))
        self._write()
        return self.summary()

    def summary(self) -> ResourceSummary:
        """Return peak resource values from collected samples."""
        ram_values = [int(row["ram_used_mib"]) for row in self._rows if row.get("ram_used_mib") not in {None, ""}]
        vram_values = [int(row["vram_used_mib"]) for row in self._rows if row.get("vram_used_mib") not in {None, ""}]
        return ResourceSummary(
            peak_ram_mib=max(ram_values) if ram_values else None,
            peak_vram_mib=max(vram_values) if vram_values else None,
            samples=len(self._rows),
        )

    def _run(self) -> None:
        while not self._stop.is_set():
            self._rows.append(
                {
                    "timestamp": utc_now(),
                    "ram_used_mib": _ram_used_mib(),
                    "vram_used_mib": _vram_used_mib(),
                }
            )
            self._stop.wait(self.interval_seconds)

    def _write(self) -> None:
        fieldnames = ["timestamp", "ram_used_mib", "vram_used_mib"]
        with self.output_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self._rows)


def _ram_used_mib() -> int | None:
    try:
        values: dict[str, int] = {}
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            key, raw_value = line.split(":", 1)
            parts = raw_value.strip().split()
            if parts:
                values[key] = int(parts[0])
        total = values.get("MemTotal")
        available = values.get("MemAvailable")
        if total is None or available is None:
            return None
        return int((total - available) / 1024)
    except Exception:
        return None


def _vram_used_mib() -> int | None:
    try:
        completed = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    if completed.returncode != 0:
        return None
    values: list[int] = []
    for line in completed.stdout.splitlines():
        stripped = line.strip()
        if stripped.isdigit():
            values.append(int(stripped))
    return max(values) if values else None
