# Smoke test: runs the pipeline on sample_data and does shallow checks.
import os
import sys
import sqlite3
import subprocess
import tempfile
import pytest

SAMPLE_DIR = "/app/sample_data"
PIPELINE = "/app/run_pipeline.py"


def test_pipeline_runs_on_sample_data():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        result = subprocess.run(
            [sys.executable, PIPELINE, SAMPLE_DIR, db_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, f"Pipeline failed:\n{result.stderr}"

        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT COUNT(*) FROM daily_summary")
        row_count = cursor.fetchone()[0]
        assert row_count > 0, "daily_summary is empty after pipeline run"

        cursor = conn.execute("SELECT SUM(revenue_total) FROM daily_summary")
        total_revenue = cursor.fetchone()[0]
        assert total_revenue > 0, "Total revenue should be positive"

        cursor = conn.execute("SELECT MIN(distinct_users) FROM daily_summary")
        min_users = cursor.fetchone()[0]
        assert min_users > 0, "distinct_users should be positive"

        conn.close()
    finally:
        os.unlink(db_path)


def test_pipeline_idempotent_on_sample_data():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        for _ in range(2):
            result = subprocess.run(
                [sys.executable, PIPELINE, SAMPLE_DIR, db_path],
                capture_output=True,
                text=True,
                timeout=60,
            )
            assert result.returncode == 0

        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT COUNT(*) FROM daily_summary")
        row_count = cursor.fetchone()[0]
        # Single-day input: expect exactly 6 groups (3 regions x 2 categories)
        assert row_count == 6, f"Expected 6 rows, got {row_count}"
        conn.close()
    finally:
        os.unlink(db_path)
