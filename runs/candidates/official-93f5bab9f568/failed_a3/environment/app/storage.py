"""
Storage module: writes aggregated summary rows to a SQLite database.
Handles schema creation, upsert logic, and connection management.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, List

import pandas as pd

from config import (
    get_logger,
    DB_TABLE_NAME,
    DB_CREATE_TABLE_SQL,
    AGG_REVENUE_COL,
    AGG_USERS_COL,
    GROUP_KEYS,
)
from utils import ensure_parent_dir

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

@contextmanager
def open_db(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    """Context manager: open a SQLite connection and close it on exit."""
    db_path = Path(db_path)
    ensure_parent_dir(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for better concurrent read performance
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema management
# ---------------------------------------------------------------------------

def init_schema(conn: sqlite3.Connection) -> None:
    """Create the daily_summary table if it does not exist."""
    conn.executescript(DB_CREATE_TABLE_SQL)
    logger.debug("Schema initialised")


def table_exists(conn: sqlite3.Connection, table: str = DB_TABLE_NAME) -> bool:
    """Return True if *table* exists in the connected database."""
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row[0] > 0


# ---------------------------------------------------------------------------
# Row-level helpers
# ---------------------------------------------------------------------------

def _row_exists(conn: sqlite3.Connection, region: str, product_category: str) -> bool:
    """
    Check whether a row with this (region, product_category) already exists.
    Returns True if found, False otherwise.
    """
    row = conn.execute(
        f"SELECT id FROM {DB_TABLE_NAME} WHERE region=? AND product_category=?",
        (region, product_category),
    ).fetchone()
    return row is not None


def _update_row(
    conn: sqlite3.Connection,
    region: str,
    product_category: str,
    revenue_total: float,
    distinct_users: int,
) -> None:
    """Update an existing summary row identified by (region, product_category)."""
    conn.execute(
        f"""
        UPDATE {DB_TABLE_NAME}
           SET revenue_total  = revenue_total + ?,
               distinct_users = distinct_users + ?
         WHERE region = ?
           AND product_category = ?
        """,
        (revenue_total, distinct_users, region, product_category),
    )


def _insert_row(
    conn: sqlite3.Connection,
    region: str,
    product_category: str,
    date: str,
    revenue_total: float,
    distinct_users: int,
) -> None:
    """Insert a new summary row."""
    conn.execute(
        f"""
        INSERT INTO {DB_TABLE_NAME}
               (region, product_category, date, revenue_total, distinct_users)
        VALUES (?, ?, ?, ?, ?)
        """,
        (region, product_category, date, revenue_total, distinct_users),
    )


# ---------------------------------------------------------------------------
# Bulk write
# ---------------------------------------------------------------------------

def upsert_summary(conn: sqlite3.Connection, agg_df: pd.DataFrame) -> int:
    """
    Write rows from *agg_df* into daily_summary using upsert semantics.

    For each row in *agg_df*, if a matching key already exists in the table
    the existing row is updated; otherwise a new row is inserted.

    Returns the number of rows written.
    """
    required = GROUP_KEYS + [AGG_REVENUE_COL, AGG_USERS_COL]
    missing = set(required) - set(agg_df.columns)
    if missing:
        raise ValueError(f"upsert_summary: missing columns {sorted(missing)}")

    written = 0
    for _, row in agg_df.iterrows():
        region = str(row["region"])
        product_category = str(row["product_category"])
        date = str(row["date"])
        revenue_total = float(row[AGG_REVENUE_COL])
        distinct_users = int(row[AGG_USERS_COL])

        if _row_exists(conn, region, product_category):
            _update_row(conn, region, product_category, revenue_total, distinct_users)
        else:
            _insert_row(conn, region, product_category, date, revenue_total, distinct_users)
        written += 1

    logger.info("upsert_summary: processed %d row(s)", written)
    return written


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def fetch_all_summary(conn: sqlite3.Connection) -> pd.DataFrame:
    """Return the full contents of daily_summary as a DataFrame."""
    return pd.read_sql_query(
        f"SELECT * FROM {DB_TABLE_NAME} ORDER BY region, product_category, date",
        conn,
    )


def fetch_summary_for_key(
    conn: sqlite3.Connection,
    region: str,
    product_category: str,
    date: str,
) -> pd.DataFrame:
    """Return summary rows for a specific (region, product_category, date) triple."""
    return pd.read_sql_query(
        f"""
        SELECT * FROM {DB_TABLE_NAME}
         WHERE region=? AND product_category=? AND date=?
        """,
        conn,
        params=(region, product_category, date),
    )


def row_count(conn: sqlite3.Connection) -> int:
    """Return total number of rows in daily_summary."""
    result = conn.execute(
        f"SELECT COUNT(*) FROM {DB_TABLE_NAME}"
    ).fetchone()
    return result[0]


def delete_all_summary(conn: sqlite3.Connection) -> None:
    """Truncate the daily_summary table."""
    conn.execute(f"DELETE FROM {DB_TABLE_NAME}")
    logger.warning("daily_summary table truncated")
