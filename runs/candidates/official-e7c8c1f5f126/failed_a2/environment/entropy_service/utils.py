"""
utils.py - Shared utilities for the entropy audit pipeline.
"""

from __future__ import annotations

import hashlib
import logging
import os
import struct
import time
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ── Logging helpers ───────────────────────────────────────────────────────────

def configure_logging(level: str = "INFO") -> None:
    """Configure root logger with timestamp format."""
    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


# ── File helpers ──────────────────────────────────────────────────────────────

def list_bin_files(directory: Path) -> List[Path]:
    """Return sorted list of .bin files in directory."""
    return sorted(directory.glob("*.bin"))


def file_sha256(path: Path, chunk_size: int = 65536) -> str:
    """Compute SHA-256 digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_read_bytes(path: Path, max_bytes: int = 100 * 1024 * 1024) -> bytes:
    """Read a file, raising ValueError if it exceeds max_bytes."""
    size = os.path.getsize(path)
    if size > max_bytes:
        raise ValueError(f"{path} is {size} bytes, exceeds limit {max_bytes}")
    return path.read_bytes()


def iter_chunks(data: bytes, chunk_size: int) -> Iterator[bytes]:
    """Yield successive chunks of exactly chunk_size bytes (last may be shorter)."""
    for i in range(0, len(data), chunk_size):
        yield data[i:i + chunk_size]


# ── Statistics helpers ────────────────────────────────────────────────────────

class RollingStats:
    """
    Welford online algorithm for computing running mean and variance.
    Suitable for streaming entropy estimates.
    """

    def __init__(self) -> None:
        self._n: int = 0
        self._mean: float = 0.0
        self._M2: float = 0.0
        self._min: float = float("inf")
        self._max: float = float("-inf")

    def update(self, value: float) -> None:
        self._n += 1
        delta = value - self._mean
        self._mean += delta / self._n
        delta2 = value - self._mean
        self._M2 += delta * delta2
        if value < self._min:
            self._min = value
        if value > self._max:
            self._max = value

    def update_batch(self, values) -> None:
        for v in values:
            self.update(float(v))

    @property
    def n(self) -> int:
        return self._n

    @property
    def mean(self) -> float:
        return self._mean if self._n > 0 else float("nan")

    @property
    def variance(self) -> float:
        if self._n < 2:
            return float("nan")
        return self._M2 / (self._n - 1)

    @property
    def std(self) -> float:
        v = self.variance
        return float("nan") if v != v else v ** 0.5

    @property
    def min(self) -> float:
        return self._min if self._n > 0 else float("nan")

    @property
    def max(self) -> float:
        return self._max if self._n > 0 else float("nan")

    def summary(self) -> dict:
        return {
            "n": self._n,
            "mean": self.mean,
            "std": self.std,
            "min": self.min,
            "max": self.max,
        }


# ── Byte-stream helpers ───────────────────────────────────────────────────────

def bytes_to_float_array(data: bytes, dtype=np.float64) -> np.ndarray:
    """Convert raw bytes to a float array with values in [0, 255]."""
    return np.frombuffer(data, dtype=np.uint8).astype(dtype)


def pack_uint32_le(values) -> bytes:
    """Pack a list of uint32 values as little-endian bytes."""
    return struct.pack(f"<{len(values)}I", *values)


def byte_frequency_table(data: bytes) -> np.ndarray:
    """Return a 256-element array of byte frequencies."""
    arr = np.frombuffer(data, dtype=np.uint8)
    counts = np.bincount(arr, minlength=256).astype(np.float64)
    return counts


def shannon_byte_entropy(data: bytes) -> float:
    """Compute Shannon entropy in bits over the byte alphabet."""
    counts = byte_frequency_table(data)
    total = counts.sum()
    if total == 0:
        return 0.0
    p = counts[counts > 0] / total
    return float(-np.sum(p * np.log2(p)))


# ── Timing helpers ────────────────────────────────────────────────────────────

class Timer:
    """Simple wall-clock timer for profiling."""

    def __init__(self) -> None:
        self._start: Optional[float] = None
        self._elapsed: float = 0.0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args):
        assert self._start is not None
        self._elapsed = time.perf_counter() - self._start

    @property
    def elapsed(self) -> float:
        return self._elapsed

    def __str__(self) -> str:
        return f"{self._elapsed * 1000:.1f} ms"


# ── Validation helpers ────────────────────────────────────────────────────────

def validate_source_id(source_id: str) -> bool:
    """Return True if source_id is a safe filesystem-compatible identifier."""
    if not source_id:
        return False
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.")
    return all(c in allowed for c in source_id) and len(source_id) <= 128


def clamp(value: float, lo: float, hi: float) -> float:
    """Clamp value to [lo, hi]."""
    return max(lo, min(hi, value))


def pretty_bytes(n: int) -> str:
    """Human-readable byte count."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"
