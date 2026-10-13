"""Apply column-type coercion, schema validation, and deduplication.

This module is called once per chunk by the pipeline driver.  It returns
two DataFrames: the validated (and cleaned) rows, and the rejected rows.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Optional

import pandas as pd

from pipeline.schema import REQUIRED_COLUMNS, split_valid_invalid, validate_columns
from pipeline.utils import get_logger

_log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Type coercion helpers
# ---------------------------------------------------------------------------


def _coerce_amount(series: pd.Series) -> pd.Series:
    """Parse *series* as float64, replacing unparseable values with NaN."""
    return pd.to_numeric(series, errors="coerce")


def _coerce_date(series: pd.Series) -> pd.Series:
    """Normalise date strings to YYYY-MM-DD; malformed values become empty."""
    def _parse(val: object) -> str:
        if pd.isna(val):
            return ""
        s = str(val).strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y%m%d"):
            try:
                return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return s  # return as-is; validator will reject it
    return series.map(_parse)


def _coerce_status(series: pd.Series) -> pd.Series:
    """Lower-case and strip whitespace from status values."""
    return series.map(
        lambda v: str(v).strip().lower() if not pd.isna(v) else ""
    )


def _coerce_record_id(series: pd.Series) -> pd.Series:
    """Strip whitespace from record_id values."""
    return series.map(lambda v: str(v).strip() if not pd.isna(v) else "")


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def _remove_duplicates(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Remove duplicate rows, keeping the first occurrence.

    Deduplication is performed on a stable subset of business columns so
    that rows with identical business data but different metadata do not
    appear twice in the output.

    Returns the deduplicated DataFrame and the number of rows dropped.
    """
    before = len(df)
    # Use a stable subset of columns for deduplication; record_id alone
    # would be too narrow because it may vary between otherwise-identical rows.
    dedup_cols = [c for c in ["name", "amount"] if c in df.columns]
    if dedup_cols:
        df = df.drop_duplicates(subset=dedup_cols, keep="first")
    dropped = before - len(df)
    if dropped:
        _log.debug("Deduplication removed %d row(s)", dropped)
    return df, dropped


# ---------------------------------------------------------------------------
# Column-type coercion
# ---------------------------------------------------------------------------


def coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of *df* with columns coerced to their canonical types."""
    df = df.copy()
    if "amount" in df.columns:
        df["amount"] = _coerce_amount(df["amount"])
    if "date" in df.columns:
        df["date"] = _coerce_date(df["date"])
    if "status" in df.columns:
        df["status"] = _coerce_status(df["status"])
    if "record_id" in df.columns:
        df["record_id"] = _coerce_record_id(df["record_id"])
    return df


# ---------------------------------------------------------------------------
# Public transform entry point
# ---------------------------------------------------------------------------


def transform_chunk(
    df: pd.DataFrame,
    *,
    run_dedup: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Process one chunk of the ingestion pipeline.

    Steps performed (in order):
    1. Validate that required columns are present.
    2. Coerce column types to their canonical representations.
    3. Remove duplicate rows.
    4. Split into valid and invalid rows using the schema validator.

    Parameters
    ----------
    df:
        Raw chunk DataFrame (all columns typed as str on entry).
    run_dedup:
        Set to False to skip the deduplication step (useful in tests).

    Returns
    -------
    (valid, rejected)
        Two DataFrames: accepted rows and rows that failed schema validation.
    """
    validate_columns(df)

    df = coerce_types(df)

    if run_dedup:
        df, _n_dropped = _remove_duplicates(df)

    valid, rejected = split_valid_invalid(df)

    _log.debug(
        "transform_chunk: %d valid, %d rejected",
        len(valid), len(rejected),
    )
    return valid, rejected


# ---------------------------------------------------------------------------
# Utility: fingerprint a row for audit logging
# ---------------------------------------------------------------------------


def row_fingerprint(row: pd.Series) -> str:
    """Return a short hex digest that uniquely identifies *row*'s content."""
    payload = "|".join(
        str(row.get(c, "")) for c in sorted(row.index)
    ).encode()
    return hashlib.sha1(payload).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Utility: summarise a DataFrame for logging
# ---------------------------------------------------------------------------


def summarise(df: pd.DataFrame, label: str = "DataFrame") -> str:
    """Return a one-line summary string for *df*."""
    return (
        f"{label}: {len(df)} rows x {len(df.columns)} cols "
        f"| columns={list(df.columns)}"
    )
