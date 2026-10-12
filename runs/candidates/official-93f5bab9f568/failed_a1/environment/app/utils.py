"""
Utility helpers used across the ETL pipeline.
General-purpose functions: path handling, data validation,
type coercion, DataFrame utilities, and misc helpers.
"""

from __future__ import annotations

import os
import re
import hashlib
import datetime
from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd

from config import get_logger, SUPPORTED_EXTENSIONS, DATE_FORMAT

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Path utilities
# ---------------------------------------------------------------------------

def list_data_files(directory: str | Path) -> List[Path]:
    """Return sorted list of supported data files in *directory*."""
    directory = Path(directory)
    if not directory.is_dir():
        raise ValueError(f"Not a directory: {directory}")
    files = sorted(
        p for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    logger.debug("Found %d data file(s) in %s", len(files), directory)
    return files


def ensure_parent_dir(path: str | Path) -> Path:
    """Create parent directories for *path* if they don't exist."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def file_checksum(path: str | Path, algorithm: str = "sha256") -> str:
    """Compute hex-digest checksum of a file."""
    h = hashlib.new(algorithm)
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Date utilities
# ---------------------------------------------------------------------------

def parse_date(value: str) -> datetime.date:
    """Parse an ISO-8601 date string to a date object."""
    try:
        return datetime.datetime.strptime(value, DATE_FORMAT).date()
    except ValueError as exc:
        raise ValueError(f"Cannot parse date {value!r}: {exc}") from exc


def date_range(start: str, end: str) -> Iterable[str]:
    """Yield ISO date strings from *start* to *end* inclusive."""
    current = parse_date(start)
    stop = parse_date(end)
    while current <= stop:
        yield current.strftime(DATE_FORMAT)
        current += datetime.timedelta(days=1)


def is_valid_date_string(value: str) -> bool:
    """Return True if *value* matches the expected date format."""
    try:
        parse_date(value)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# DataFrame utilities
# ---------------------------------------------------------------------------

def drop_duplicates_stable(df: pd.DataFrame, subset: Optional[List[str]] = None) -> pd.DataFrame:
    """Drop duplicate rows, keeping the first occurrence."""
    before = len(df)
    df = df.drop_duplicates(subset=subset, keep="first")
    dropped = before - len(df)
    if dropped:
        logger.debug("Dropped %d duplicate row(s)", dropped)
    return df


def coerce_numeric(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    """Coerce specified columns to numeric, turning errors into NaN."""
    df = df.copy()
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def filter_positive(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Keep only rows where *column* > 0 (after dropping NaN)."""
    before = len(df)
    df = df[df[column].notna() & (df[column] > 0)]
    logger.debug("filter_positive('%s'): %d -> %d rows", column, before, len(df))
    return df


def strip_string_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Strip leading/trailing whitespace from all string columns."""
    df = df.copy()
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].str.strip()
    return df


def rename_columns_lower(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase all column names."""
    df.columns = [c.lower() for c in df.columns]
    return df


# ---------------------------------------------------------------------------
# String utilities
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Convert text to a lowercase slug (letters, digits, hyphens only)."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def truncate(text: str, max_len: int = 80, suffix: str = "...") -> str:
    """Truncate *text* to *max_len* characters."""
    if len(text) <= max_len:
        return text
    return text[: max_len - len(suffix)] + suffix


def safe_str(value) -> str:
    """Convert *value* to string, returning empty string for None/NaN."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)


# ---------------------------------------------------------------------------
# Numeric utilities
# ---------------------------------------------------------------------------

def clamp(value: float, lo: float, hi: float) -> float:
    """Clamp *value* to the range [*lo*, *hi*]."""
    return max(lo, min(hi, value))


def round_half_up(value: float, decimals: int = 2) -> float:
    """Round *value* to *decimals* places using round-half-up rule."""
    from decimal import Decimal, ROUND_HALF_UP
    d = Decimal(str(value))
    quantizer = Decimal(10) ** -decimals
    return float(d.quantize(quantizer, rounding=ROUND_HALF_UP))


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Divide, returning *default* if denominator is zero."""
    if denominator == 0:
        return default
    return numerator / denominator


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

def flatten(nested: Iterable) -> List:
    """Flatten one level of nesting."""
    result = []
    for item in nested:
        if isinstance(item, (list, tuple)):
            result.extend(item)
        else:
            result.append(item)
    return result


def chunk_list(lst: list, size: int) -> Iterable[list]:
    """Yield successive chunks of *lst* of length *size*."""
    for i in range(0, len(lst), size):
        yield lst[i: i + size]


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base*, returning a new dict."""
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = deep_merge(result[key], val)
        else:
            result[key] = val
    return result
