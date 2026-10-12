"""
Aggregation module: groups transformed records by (region, product_category, date)
and computes summary statistics for each group.
"""

from __future__ import annotations

from typing import List

import pandas as pd

from config import (
    get_logger,
    GROUP_KEYS,
    AGG_REVENUE_COL,
    AGG_USERS_COL,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_input(df: pd.DataFrame) -> None:
    """Ensure the DataFrame has all columns needed for aggregation."""
    required = set(GROUP_KEYS + ["revenue", "user_id"])
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"aggregate: input DataFrame missing columns: {sorted(missing)}"
        )


def _compute_group_stats(group: pd.DataFrame) -> pd.Series:
    """
    Compute per-group aggregates.

    Returns a Series with:
      revenue_total  - sum of revenue values in the group
      distinct_users - count of unique user identifiers in the group
    """
    revenue_total = group["revenue"].sum()
    # Count how many user records are in this group
    distinct_users = len(group["user_id"])

    return pd.Series(
        {AGG_REVENUE_COL: revenue_total, AGG_USERS_COL: distinct_users}
    )


def _log_aggregation_summary(agg_df: pd.DataFrame) -> None:
    """Log a brief summary of the aggregated result."""
    logger.info(
        "Aggregation produced %d group(s) across %d region(s), "
        "%d category(ies), %d date(s)",
        len(agg_df),
        agg_df["region"].nunique(),
        agg_df["product_category"].nunique(),
        agg_df["date"].nunique(),
    )
    logger.debug(
        "Revenue range: %.4f - %.4f",
        agg_df[AGG_REVENUE_COL].min(),
        agg_df[AGG_REVENUE_COL].max(),
    )


# ---------------------------------------------------------------------------
# Optional incremental accumulation helpers
# ---------------------------------------------------------------------------

def accumulate(existing: pd.DataFrame, new_agg: pd.DataFrame) -> pd.DataFrame:
    """
    Merge *new_agg* into *existing* aggregated data.

    Both DataFrames must have columns: region, product_category, date,
    revenue_total, distinct_users.

    For matching (region, product_category, date) triples:
      - revenue_total values are summed
      - distinct_users values are summed
    New triples in *new_agg* that don't exist in *existing* are appended.
    """
    if existing.empty:
        return new_agg.copy()
    if new_agg.empty:
        return existing.copy()

    combined = pd.concat([existing, new_agg], ignore_index=True)
    merged = (
        combined
        .groupby(GROUP_KEYS, as_index=False)
        .agg(
            revenue_total=(AGG_REVENUE_COL, "sum"),
            distinct_users=(AGG_USERS_COL, "sum"),
        )
    )
    return merged


def filter_groups_by_min_revenue(
    agg_df: pd.DataFrame, min_revenue: float = 0.0
) -> pd.DataFrame:
    """Drop aggregate rows whose revenue_total is at or below *min_revenue*."""
    before = len(agg_df)
    agg_df = agg_df[agg_df[AGG_REVENUE_COL] > min_revenue].copy()
    dropped = before - len(agg_df)
    if dropped:
        logger.debug("Dropped %d low-revenue aggregate row(s)", dropped)
    return agg_df


def top_n_groups(
    agg_df: pd.DataFrame, n: int = 10, by: str = AGG_REVENUE_COL
) -> pd.DataFrame:
    """Return the top *n* aggregate rows sorted descending by *by*."""
    return agg_df.nlargest(n, by).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def aggregate(df: pd.DataFrame) -> pd.DataFrame:
    """
    Group *df* by (region, product_category, date) and compute
    revenue_total and distinct_users for each group.

    Parameters
    ----------
    df : pd.DataFrame
        Transformed event-level DataFrame with at least the columns:
        region, product_category, date, revenue, user_id.

    Returns
    -------
    pd.DataFrame
        One row per (region, product_category, date) triple with columns:
        region, product_category, date, revenue_total, distinct_users.
    """
    _validate_input(df)
    logger.info("Aggregating %d row(s) by %s", len(df), GROUP_KEYS)

    agg_df = (
        df
        .groupby(GROUP_KEYS, as_index=False)
        .apply(_compute_group_stats)
        .reset_index(drop=True)
    )

    # Ensure correct types
    agg_df[AGG_REVENUE_COL] = agg_df[AGG_REVENUE_COL].astype(float)
    agg_df[AGG_USERS_COL] = agg_df[AGG_USERS_COL].astype(int)

    _log_aggregation_summary(agg_df)
    return agg_df
