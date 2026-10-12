"""
Transformation module: normalises raw ingested data before aggregation.
Applies field cleaning, validation, filtering, and derived-column logic.
"""

from __future__ import annotations

import re
from typing import Dict, List

import pandas as pd

from config import (
    get_logger,
    REVENUE_MIN_THRESHOLD,
    DATE_FORMAT,
    GROUP_KEYS,
)
from utils import (
    filter_positive,
    is_valid_date_string,
    safe_str,
    strip_string_columns,
    coerce_numeric,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Field normalisation helpers
# ---------------------------------------------------------------------------

def _normalise_region(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalise the 'region' column:
    - Strip whitespace (already done in ingestion, but be defensive)
    - Uppercase the first letter of each word
    - Replace internal runs of whitespace with a single space
    """
    df = df.copy()
    df["region"] = (
        df["region"]
        .str.strip()
        .str.lower()
        .str.replace(r"\s+", " ", regex=True)
        .str.title()
    )
    return df


def _normalise_product_category(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalise 'product_category':
    - Strip whitespace
    - Lowercase everything
    - Replace spaces with underscores for consistency
    """
    df = df.copy()
    df["product_category"] = (
        df["product_category"]
        .str.strip()
        .str.lower()
        .str.replace(r"\s+", "_", regex=True)
    )
    return df


def _normalise_user_id(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure user_id is a clean string with no surrounding whitespace."""
    df = df.copy()
    df["user_id"] = df["user_id"].apply(safe_str).str.strip()
    return df


def _normalise_date(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate and normalise the 'date' column.
    Rows with unparseable dates are dropped with a warning.
    """
    df = df.copy()
    valid_mask = df["date"].apply(is_valid_date_string)
    bad_count = (~valid_mask).sum()
    if bad_count:
        logger.warning("Dropping %d row(s) with invalid date format", bad_count)
    df = df[valid_mask].copy()
    # Re-format dates to ensure canonical YYYY-MM-DD
    df["date"] = pd.to_datetime(df["date"], format=DATE_FORMAT).dt.strftime(DATE_FORMAT)
    return df


def _normalise_revenue(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce revenue to float and drop rows at or below the minimum threshold."""
    df = coerce_numeric(df, ["revenue"])
    before = len(df)
    df = df[df["revenue"].notna() & (df["revenue"] > REVENUE_MIN_THRESHOLD)].copy()
    dropped = before - len(df)
    if dropped:
        logger.warning(
            "Dropped %d row(s) with revenue <= %s", dropped, REVENUE_MIN_THRESHOLD
        )
    return df


# ---------------------------------------------------------------------------
# Derived columns
# ---------------------------------------------------------------------------

def _add_year_month(df: pd.DataFrame) -> pd.DataFrame:
    """Add 'year_month' column (YYYY-MM) derived from 'date'."""
    df = df.copy()
    df["year_month"] = df["date"].str[:7]  # fast slice; date already validated
    return df


def _add_revenue_band(df: pd.DataFrame) -> pd.DataFrame:
    """
    Classify each revenue value into a band:
      low  : revenue < 10
      mid  : 10 <= revenue < 100
      high : revenue >= 100
    """
    df = df.copy()

    def _band(v: float) -> str:
        if v < 10:
            return "low"
        if v < 100:
            return "mid"
        return "high"

    df["revenue_band"] = df["revenue"].apply(_band)
    return df


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def _filter_known_regions(df: pd.DataFrame, known: List[str]) -> pd.DataFrame:
    """Keep only rows whose normalised region appears in *known*."""
    if not known:
        return df
    before = len(df)
    df = df[df["region"].isin(known)].copy()
    dropped = before - len(df)
    if dropped:
        logger.debug("Filtered out %d row(s) from unknown regions", dropped)
    return df


def _filter_empty_user_ids(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows where user_id is empty or whitespace."""
    before = len(df)
    df = df[df["user_id"].str.len() > 0].copy()
    dropped = before - len(df)
    if dropped:
        logger.warning("Dropped %d row(s) with empty user_id", dropped)
    return df


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def transform(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply the full transformation pipeline to a raw ingested DataFrame.

    Steps (in order):
      1. Normalise region, product_category, user_id, date, revenue
      2. Filter out empty user_ids
      3. Add derived columns (year_month, revenue_band)

    Returns a cleaned DataFrame ready for aggregation.
    """
    logger.info("Starting transformation on %d rows", len(df))

    df = _normalise_region(df)
    df = _normalise_product_category(df)
    df = _normalise_user_id(df)
    df = _normalise_date(df)
    df = _normalise_revenue(df)
    df = _filter_empty_user_ids(df)
    df = _add_year_month(df)
    df = _add_revenue_band(df)

    logger.info("Transformation complete: %d rows remaining", len(df))
    return df


def transform_field_report(df: pd.DataFrame) -> Dict[str, int]:
    """
    Return a summary dict of field-level statistics after transformation.
    Useful for logging and diagnostics.
    """
    return {
        "total_rows": len(df),
        "unique_regions": df["region"].nunique(),
        "unique_categories": df["product_category"].nunique(),
        "unique_dates": df["date"].nunique(),
        "unique_users": df["user_id"].nunique(),
        "revenue_band_low": int((df["revenue_band"] == "low").sum()),
        "revenue_band_mid": int((df["revenue_band"] == "mid").sum()),
        "revenue_band_high": int((df["revenue_band"] == "high").sum()),
    }
