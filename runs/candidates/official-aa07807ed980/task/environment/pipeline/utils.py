"""Logging and miscellaneous helpers for the ingestion pipeline."""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Logger factory
# ---------------------------------------------------------------------------

_LOGGERS: dict[str, logging.Logger] = {}


def get_logger(
    name: str,
    level: int = logging.INFO,
    fmt: Optional[str] = None,
) -> logging.Logger:
    """Return a named logger, creating it on first call.

    Subsequent calls with the same *name* return the cached logger without
    adding duplicate handlers.
    """
    if name in _LOGGERS:
        return _LOGGERS[name]

    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        if fmt is None:
            fmt = "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
        handler.setFormatter(logging.Formatter(fmt, datefmt="%H:%M:%S"))
        logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    _LOGGERS[name] = logger
    return logger


# ---------------------------------------------------------------------------
# File-system helpers
# ---------------------------------------------------------------------------


def ensure_dir(path: str | Path) -> Path:
    """Create *path* and all parents if they do not exist; return a Path."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def safe_remove(path: str | Path) -> bool:
    """Delete *path* if it exists.  Return True when a file was removed."""
    p = Path(path)
    try:
        p.unlink()
        return True
    except FileNotFoundError:
        return False


def list_files(directory: str | Path, suffix: str = "") -> list[Path]:
    """Return a sorted list of files in *directory* with the given *suffix*."""
    d = Path(directory)
    if not d.is_dir():
        return []
    files = sorted(f for f in d.iterdir() if f.is_file() and f.name.endswith(suffix))
    return files


# ---------------------------------------------------------------------------
# Timing context manager
# ---------------------------------------------------------------------------


class Timer:
    """Simple wall-clock timer usable as a context manager.

    Usage::

        with Timer() as t:
            do_work()
        print(f"Elapsed: {t.elapsed:.3f}s")
    """

    def __init__(self) -> None:
        self._start: float = 0.0
        self.elapsed: float = 0.0

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_: object) -> None:
        self.elapsed = time.perf_counter() - self._start


# ---------------------------------------------------------------------------
# Pretty-print helpers
# ---------------------------------------------------------------------------


def human_size(num_bytes: int) -> str:
    """Return a human-readable file size string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0  # type: ignore[assignment]
    return f"{num_bytes:.1f} PB"


def progress_bar(
    current: int,
    total: int,
    width: int = 40,
    prefix: str = "",
) -> str:
    """Return a simple ASCII progress bar string."""
    frac = current / total if total else 0.0
    filled = int(frac * width)
    bar = "#" * filled + "-" * (width - filled)
    pct = int(frac * 100)
    return f"{prefix}[{bar}] {pct:3d}% ({current}/{total})"


# ---------------------------------------------------------------------------
# Environment introspection
# ---------------------------------------------------------------------------


def get_env(key: str, default: str = "") -> str:
    """Return an environment variable, falling back to *default*."""
    return os.environ.get(key, default)


def require_env(key: str) -> str:
    """Return an environment variable or raise RuntimeError if absent."""
    val = os.environ.get(key)
    if val is None:
        raise RuntimeError(f"Required environment variable {key!r} is not set.")
    return val
