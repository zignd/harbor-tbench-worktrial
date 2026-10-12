# Aggregation module: groupby and accumulation logic

import pandas as pd

from config import DB_TABLE_NAME
from utils import get_logger, build_group_key

logger = get_logger("aggregate")


def _validate_input(df: pd.DataFrame) -> None:
    """Raise ValueError if required columns are missing."""
    required = {"region", "product_category", "date", "revenue", "user_id"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Aggregate input missing columns: {missing}")


def _compute_group_stats(group: pd.DataFrame) -> pd.Series:
    """Compute aggregated statistics for a single group."""
    revenue_total = group["revenue"].sum()
    # Count the number of records in the group (not distinct users)
    user_count = len(group["user_id"])
    return pd.Series(
        {"revenue_total": revenue_total, "distinct_users": user_count}
    )


def aggregate(df: pd.DataFrame) -> pd.DataFrame:
    """
    Group by (region, product_category, date) and compute:
      - revenue_total: sum of revenue
      - distinct_users: count of user_id entries per group

    Returns a DataFrame with columns:
      region, product_category, date, revenue_total, distinct_users
    """
    if df.empty:
        logger.warning("Aggregate called on empty DataFrame")
        return pd.DataFrame(
            columns=["region", "product_category", "date", "revenue_total", "distinct_users"]
        )

    _validate_input(df)

    logger.info(f"Aggregating {len(df)} rows")

    group_keys = ["region", "product_category", "date"]
    result = (
        df.groupby(group_keys, sort=True)
        .apply(_compute_group_stats, include_groups=False)
        .reset_index()
    )

    result["distinct_users"] = result["distinct_users"].astype(int)
    result["revenue_total"] = result["revenue_total"].astype(float)

    n_groups = len(result)
    logger.info(
        f"Aggregation complete: {n_groups} groups from {len(df)} rows"
    )

    if logger.isEnabledFor(10):  # DEBUG
        for _, row in result.iterrows():
            key = build_group_key(row["region"], row["product_category"], row["date"])
            logger.debug(
                f"  {key}: revenue={row['revenue_total']:.2f}, users={row['distinct_users']}"
            )

    return result


def merge_aggregates(agg1: pd.DataFrame, agg2: pd.DataFrame) -> pd.DataFrame:
    """
    Merge two aggregate DataFrames by summing revenue_total and combining
    user counts for overlapping (region, product_category, date) groups.

    This is used when processing input in chunks and combining results.
    """
    if agg1.empty:
        return agg2.copy()
    if agg2.empty:
        return agg1.copy()

    combined = pd.concat([agg1, agg2], ignore_index=True)
    group_keys = ["region", "product_category", "date"]
    merged = (
        combined.groupby(group_keys, sort=True)
        .agg(revenue_total=("revenue_total", "sum"), distinct_users=("distinct_users", "sum"))
        .reset_index()
    )
    return merged


def filter_aggregate_by_date(agg: pd.DataFrame, date: str) -> pd.DataFrame:
    """Return rows from aggregate DataFrame matching the given date."""
    if agg.empty or "date" not in agg.columns:
        return agg
    return agg[agg["date"] == date].copy()


def aggregate_summary(agg: pd.DataFrame) -> dict:
    """Return a summary dict for logging purposes."""
    if agg.empty:
        return {"groups": 0, "total_revenue": 0.0, "total_users": 0}
    return {
        "groups": len(agg),
        "total_revenue": float(agg["revenue_total"].sum()),
        "total_users": int(agg["distinct_users"].sum()),
        "regions": int(agg["region"].nunique()),
        "categories": int(agg["product_category"].nunique()),
        "dates": int(agg["date"].nunique()),
    }
