# Storage module: SQLite writer

import sqlite3
from typing import Optional

import pandas as pd

from config import DB_SCHEMA, DB_TABLE_NAME
from utils import get_logger

logger = get_logger("storage")


def init_db(db_path: str) -> sqlite3.Connection:
    """Open (or create) the SQLite database and apply the schema."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.executescript(DB_SCHEMA)
    conn.commit()
    logger.info(f"Database initialized: {db_path}")
    return conn


def _row_exists(conn: sqlite3.Connection, region: str, product_category: str, date: str) -> Optional[int]:
    """Return the id of an existing row for (region, product_category) or None."""
    cursor = conn.execute(
        "SELECT id FROM daily_summary WHERE region = ? AND product_category = ?",
        (region, product_category),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def _upsert_row(
    conn: sqlite3.Connection,
    region: str,
    product_category: str,
    date: str,
    revenue_total: float,
    distinct_users: int,
) -> None:
    """Insert or update a single daily_summary row."""
    existing_id = _row_exists(conn, region, product_category, date)
    if existing_id is not None:
        conn.execute(
            """
            UPDATE daily_summary
            SET revenue_total = revenue_total + ?,
                distinct_users = ?
            WHERE id = ?
            """,
            (revenue_total, distinct_users, existing_id),
        )
    else:
        conn.execute(
            """
            INSERT INTO daily_summary (region, product_category, date, revenue_total, distinct_users)
            VALUES (?, ?, ?, ?, ?)
            """,
            (region, product_category, date, revenue_total, distinct_users),
        )


def write_aggregates(conn: sqlite3.Connection, agg: pd.DataFrame) -> int:
    """
    Write aggregate rows to daily_summary.
    Returns the number of rows written.
    """
    if agg.empty:
        logger.warning("write_aggregates called with empty DataFrame")
        return 0

    logger.info(f"Writing {len(agg)} aggregate rows to {DB_TABLE_NAME}")

    count = 0
    for _, row in agg.iterrows():
        _upsert_row(
            conn,
            region=str(row["region"]),
            product_category=str(row["product_category"]),
            date=str(row["date"]),
            revenue_total=float(row["revenue_total"]),
            distinct_users=int(row["distinct_users"]),
        )
        count += 1

    conn.commit()
    logger.info(f"Committed {count} rows")
    return count


def read_summary(conn: sqlite3.Connection) -> pd.DataFrame:
    """Read all rows from daily_summary and return as a DataFrame."""
    return pd.read_sql_query(
        "SELECT region, product_category, date, revenue_total, distinct_users FROM daily_summary ORDER BY region, product_category, date",
        conn,
    )


def get_row_count(conn: sqlite3.Connection) -> int:
    """Return the number of rows in daily_summary."""
    cursor = conn.execute("SELECT COUNT(*) FROM daily_summary")
    return cursor.fetchone()[0]


def close_db(conn: sqlite3.Connection) -> None:
    """Commit any pending changes and close the connection."""
    try:
        conn.commit()
    finally:
        conn.close()
    logger.info("Database connection closed")
