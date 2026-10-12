# Transformation module: field normalization and cleaning

import pandas as pd

from config import CSV_COLUMNS
from utils import (
    get_logger,
    normalize_region,
    normalize_category,
    drop_invalid_rows,
    safe_strip,
    validate_date_string,
)

logger = get_logger("transform")


def _normalize_string_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Strip whitespace from string columns."""
    str_cols = ["event_id", "user_id", "region", "product_category", "date"]
    for col in str_cols:
        if col in df.columns:
            df[col] = df[col].apply(safe_strip)
    return df


def _normalize_region_column(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize region values."""
    if "region" in df.columns:
        df["region"] = df["region"].apply(normalize_region)
    return df


def _normalize_category_column(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize product_category values."""
    if "product_category" in df.columns:
        df["product_category"] = df["product_category"].apply(normalize_category)
    return df


def _validate_and_clean(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows with invalid revenue or dates."""
    df = drop_invalid_rows(df, logger)
    return df


def _drop_duplicate_events(df: pd.DataFrame) -> pd.DataFrame:
    """Drop exact duplicate event_id entries (keep first occurrence)."""
    before = len(df)
    df = df.drop_duplicates(subset=["event_id"], keep="first")
    after = len(df)
    if before - after:
        logger.info(f"Dropped {before - after} duplicate event_id rows")
    return df


def _cast_revenue(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure revenue column is float64."""
    if "revenue" in df.columns:
        df["revenue"] = df["revenue"].astype(float)
    return df


def _fill_missing_strings(df: pd.DataFrame) -> pd.DataFrame:
    """Replace empty strings in key columns with a placeholder."""
    for col in ["region", "product_category"]:
        if col in df.columns:
            mask = df[col] == ""
            if mask.any():
                logger.warning(f"Filling {mask.sum()} empty '{col}' values with 'UNKNOWN'")
                df.loc[mask, col] = "UNKNOWN"
    return df


def _standardize_date(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure date column is in YYYY-MM-DD format (drop rows that aren't)."""
    if "date" not in df.columns:
        return df
    # Try to parse and reformat dates that may have been read differently
    def _coerce_date(val):
        if validate_date_string(val):
            return val
        # Try pandas parser
        try:
            return pd.Timestamp(val).strftime("%Y-%m-%d")
        except Exception:
            return None

    df["date"] = df["date"].apply(_coerce_date)
    before = len(df)
    df = df.dropna(subset=["date"])
    after = len(df)
    if before - after:
        logger.warning(f"Dropped {before - after} rows with unparseable dates")
    return df


def _add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add any derived columns needed downstream."""
    # Currently no additional derived columns are needed.
    # This is a hook for future transformations.
    return df


def _log_transform_summary(df: pd.DataFrame, stage: str) -> None:
    """Log summary statistics after a transformation stage."""
    logger.debug(
        f"After {stage}: {len(df)} rows, "
        f"regions={df['region'].nunique() if 'region' in df.columns else 'N/A'}, "
        f"categories={df['product_category'].nunique() if 'product_category' in df.columns else 'N/A'}"
    )


def transform(df: pd.DataFrame) -> pd.DataFrame:
    """Run all transformation steps on the ingested DataFrame."""
    if df.empty:
        logger.warning("Transform called on empty DataFrame")
        return df

    logger.info(f"Starting transform: {len(df)} rows")

    df = _normalize_string_columns(df)
    _log_transform_summary(df, "normalize_strings")

    df = _normalize_region_column(df)
    _log_transform_summary(df, "normalize_region")

    df = _normalize_category_column(df)
    _log_transform_summary(df, "normalize_category")

    df = _standardize_date(df)
    _log_transform_summary(df, "standardize_date")

    df = _cast_revenue(df)
    _log_transform_summary(df, "cast_revenue")

    df = _validate_and_clean(df)
    _log_transform_summary(df, "validate_and_clean")

    df = _drop_duplicate_events(df)
    _log_transform_summary(df, "drop_duplicate_events")

    df = _fill_missing_strings(df)
    _log_transform_summary(df, "fill_missing_strings")

    df = _add_derived_columns(df)
    _log_transform_summary(df, "add_derived_columns")

    logger.info(f"Transform complete: {len(df)} rows")
    return df
