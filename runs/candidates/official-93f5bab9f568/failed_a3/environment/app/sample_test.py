"""
Smoke test for the ETL pipeline using the bundled sample data.
Runs the pipeline on /app/sample_data/ and checks basic sanity:
- The pipeline exits without error.
- The daily_summary table has at least one row.
- Every row has revenue_total > 0 and distinct_users > 0.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile

import pytest

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE_DATA = os.path.join(APP_DIR, "sample_data")
PIPELINE = os.path.join(APP_DIR, "run_pipeline.py")


@pytest.fixture(scope="module")
def db_path(tmp_path_factory):
    """Run the pipeline once and return the path to the resulting database."""
    db = str(tmp_path_factory.mktemp("db") / "sample.db")
    result = subprocess.run(
        [sys.executable, PIPELINE, SAMPLE_DATA, db],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Pipeline exited with code {result.returncode}\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )
    return db


def test_table_has_rows(db_path):
    """daily_summary must contain at least one row."""
    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM daily_summary").fetchone()[0]
    conn.close()
    assert count > 0, "daily_summary is empty after pipeline run"


def test_revenue_positive(db_path):
    """Every row must have revenue_total > 0."""
    conn = sqlite3.connect(db_path)
    bad = conn.execute(
        "SELECT COUNT(*) FROM daily_summary WHERE revenue_total <= 0"
    ).fetchone()[0]
    conn.close()
    assert bad == 0, f"{bad} row(s) have revenue_total <= 0"


def test_distinct_users_positive(db_path):
    """Every row must have distinct_users > 0."""
    conn = sqlite3.connect(db_path)
    bad = conn.execute(
        "SELECT COUNT(*) FROM daily_summary WHERE distinct_users <= 0"
    ).fetchone()[0]
    conn.close()
    assert bad == 0, f"{bad} row(s) have distinct_users <= 0"


def test_no_null_keys(db_path):
    """Key columns must not be NULL."""
    conn = sqlite3.connect(db_path)
    bad = conn.execute(
        """
        SELECT COUNT(*) FROM daily_summary
         WHERE region IS NULL
            OR product_category IS NULL
            OR date IS NULL
        """
    ).fetchone()[0]
    conn.close()
    assert bad == 0, f"{bad} row(s) have NULL key columns"
