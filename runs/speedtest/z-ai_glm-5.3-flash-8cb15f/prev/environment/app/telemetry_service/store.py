"""On-demand snapshot loading for the two legacy log directories."""

from __future__ import annotations

from pathlib import Path
import threading

from .access import decode_directory as decode_frontend
from .attribution import AttributionResult, attribute
from .bpack import decode_directory as decode_backend

FRONTEND_DIR = Path("/var/log/telemetry/frontend")
BACKEND_DIR = Path("/var/log/telemetry/backend")


def _signature(directory: Path, pattern: str) -> tuple[tuple[str, int, int], ...]:
    return tuple(
        (path.name, path.stat().st_size, path.stat().st_mtime_ns)
        for path in sorted(directory.glob(pattern), key=lambda item: item.name)
    )


class TelemetryStore:
    def __init__(self, frontend_dir: str | Path = FRONTEND_DIR, backend_dir: str | Path = BACKEND_DIR):
        self._frontend_dir = Path(frontend_dir)
        self._backend_dir = Path(backend_dir)
        self._lock = threading.RLock()
        self._signature: tuple[tuple[str, int, int], ...] | None = None
        self._result: AttributionResult | None = None

    def snapshot(self) -> AttributionResult:
        with self._lock:
            signature = _signature(self._frontend_dir, "*.tsv") + _signature(
                self._backend_dir, "*.bpack"
            )
            if self._result is None or signature != self._signature:
                frontend = decode_frontend(self._frontend_dir)
                backend = decode_backend(self._backend_dir)
                self._result = attribute(frontend, backend)
                self._signature = signature
            return self._result
