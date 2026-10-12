"""
Logging and miscellaneous helpers for the ingestion pipeline.
None of these functions are directly involved in chunk I/O or
data transformation logic.
"""

import logging
import os
import sys
import time
from pathlib import Path


LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

_configured = False


def configure_logging(level=logging.INFO, log_file=None):
    """
    Set up root logger.  Call once at program start.
    Subsequent calls are no-ops.
    """
    global _configured
    if _configured:
        return
    handlers = [logging.StreamHandler(sys.stderr)]
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
    logging.basicConfig(format=LOG_FORMAT, datefmt=DATE_FORMAT,
                        level=level, handlers=handlers)
    _configured = True


def get_logger(name):
    """Return a named logger, configuring root logging if needed."""
    configure_logging()
    return logging.getLogger(name)


class Timer:
    """Simple wall-clock timer for coarse profiling."""

    def __init__(self, label=""):
        self.label = label
        self._start = None
        self._end = None

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_):
        self._end = time.perf_counter()

    @property
    def elapsed(self):
        if self._end is None:
            return time.perf_counter() - self._start
        return self._end - self._start

    def __str__(self):
        label = f"{self.label}: " if self.label else ""
        return f"{label}{self.elapsed:.3f}s"


def ensure_dir(path):
    """Create directory (and parents) if it does not already exist."""
    Path(path).mkdir(parents=True, exist_ok=True)


def count_lines(path, skip_header=True):
    """
    Count non-empty lines in a text file.
    If skip_header is True the first line is not counted.
    """
    n = 0
    with open(path, "r", encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if i == 0 and skip_header:
                continue
            if line.strip():
                n += 1
    return n


def human_size(n_bytes):
    """Return a human-readable string for a byte count."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n_bytes < 1024:
            return f"{n_bytes:.1f} {unit}"
        n_bytes /= 1024
    return f"{n_bytes:.1f} PB"


def safe_int(value, default=0):
    """Convert value to int, returning default on failure."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def chunked(iterable, size):
    """
    Yield successive slices of *iterable* each of length *size*.
    The final slice may be shorter.
    """
    buf = []
    for item in iterable:
        buf.append(item)
        if len(buf) == size:
            yield buf
            buf = []
    if buf:
        yield buf


def flatten(list_of_lists):
    """Flatten one level of nesting."""
    return [item for sublist in list_of_lists for item in sublist]


def clamp(value, lo, hi):
    """Clamp *value* to the closed interval [*lo*, *hi*]."""
    return max(lo, min(hi, value))


def read_env(key, default=None, cast=str):
    """
    Read an environment variable, optionally casting its type.
    Returns *default* if the variable is absent or empty.
    """
    raw = os.environ.get(key, "")
    if not raw:
        return default
    try:
        return cast(raw)
    except (ValueError, TypeError):
        return default
