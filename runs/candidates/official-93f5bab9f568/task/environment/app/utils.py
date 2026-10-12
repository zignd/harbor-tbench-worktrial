# Utility helpers for the ETL pipeline

import logging
import os
import re
from datetime import datetime
from typing import List, Optional

import pandas as pd

from config import LOG_LEVEL, MIN_DATE, MAX_DATE, MIN_REVENUE, MAX_REVENUE


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger for the given module name."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)
    return logger


def discover_csv_files(input_dir: str) -> List[str]:
    """Return sorted list of CSV file paths in input_dir."""
    if not os.path.isdir(input_dir):
        raise ValueError(f"Input directory does not exist: {input_dir}")
    files = [
        os.path.join(input_dir, f)
        for f in sorted(os.listdir(input_dir))
        if f.lower().endswith(".csv")
    ]
    return files


def validate_date_string(date_str: str) -> bool:
    """Return True if date_str is a valid YYYY-MM-DD string."""
    if not isinstance(date_str, str):
        return False
    pattern = r"^\d{4}-\d{2}-\d{2}$"
    if not re.match(pattern, date_str):
        return False
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return MIN_DATE <= date_str <= MAX_DATE
    except ValueError:
        return False


def validate_revenue(value) -> bool:
    """Return True if value is a finite float within allowed range."""
    try:
        v = float(value)
        return MIN_REVENUE <= v <= MAX_REVENUE and not (v != v)  # NaN check
    except (TypeError, ValueError):
        return False


def safe_strip(value) -> str:
    """Strip whitespace from a value, returning empty string for non-strings."""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip() if value is not None else ""


def normalize_region(region: str) -> str:
    """Normalize region string: strip and upper-case."""
    return safe_strip(region).upper()


def normalize_category(category: str) -> str:
    """Normalize product_category string: strip and title-case."""
    return safe_strip(category).title()


def summarize_dataframe(df: pd.DataFrame, label: str = "") -> str:
    """Return a short summary string for logging."""
    tag = f"[{label}] " if label else ""
    return (
        f"{tag}rows={len(df)}, cols={list(df.columns)}, "
        f"memory={df.memory_usage(deep=True).sum() // 1024}KB"
    )


def coerce_revenue(series: pd.Series) -> pd.Series:
    """Coerce a Series to float, replacing unparseable values with NaN."""
    return pd.to_numeric(series, errors="coerce")


def drop_invalid_rows(df: pd.DataFrame, logger: logging.Logger) -> pd.DataFrame:
    """Drop rows with NaN revenue or invalid dates, logging counts."""
    initial = len(df)
    df = df.dropna(subset=["revenue"])
    after_rev = len(df)
    if initial - after_rev:
        logger.warning(f"Dropped {initial - after_rev} rows with invalid revenue")

    valid_date_mask = df["date"].apply(validate_date_string)
    df = df[valid_date_mask]
    after_date = len(df)
    if after_rev - after_date:
        logger.warning(f"Dropped {after_rev - after_date} rows with invalid dates")

    return df


def chunk_dataframe(df: pd.DataFrame, chunk_size: int):
    """Yield successive chunk_size-row chunks from df."""
    for start in range(0, len(df), chunk_size):
        yield df.iloc[start : start + chunk_size]


def format_elapsed(seconds: float) -> str:
    """Format elapsed seconds as a human-readable string."""
    if seconds < 60:
        return f"{seconds:.2f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}m {secs:.1f}s"


def ensure_dir(path: str) -> None:
    """Create directory at path if it does not exist."""
    os.makedirs(path, exist_ok=True)


def safe_float(value, default: float = 0.0) -> float:
    """Convert value to float, returning default on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_group_key(region: str, category: str, date: str) -> str:
    """Build a canonical string key for a (region, category, date) triple."""
    return f"{region}|{category}|{date}"


def parse_group_key(key: str):
    """Parse a group key back into (region, category, date)."""
    parts = key.split("|")
    if len(parts) != 3:
        raise ValueError(f"Invalid group key: {key}")
    return parts[0], parts[1], parts[2]
