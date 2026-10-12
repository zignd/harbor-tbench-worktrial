"""
CLI entry point for the ETL pipeline.

Usage:
    python /app/run_pipeline.py <input_dir> <db_path>

Reads CSV event records from <input_dir>, transforms and aggregates them,
then writes per-(region, product_category, date) summaries to <db_path>.
"""

from __future__ import annotations

import sys
import os
import argparse
import traceback

# Ensure the app directory is on sys.path so relative imports work
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

from config import get_logger
from ingest import ingest_directory
from transform import transform, transform_field_report
from aggregate import aggregate
from storage import open_db, init_schema, upsert_summary, row_count

logger = get_logger("run_pipeline")


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the ETL pipeline: ingest CSV files, aggregate, write to SQLite."
    )
    parser.add_argument(
        "input_dir",
        help="Directory containing input CSV files.",
    )
    parser.add_argument(
        "db_path",
        help="Path to the SQLite database file (created if absent).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO).",
    )
    return parser.parse_args(argv)


def run(input_dir: str, db_path: str) -> None:
    """Execute the full ETL pipeline."""
    logger.info("=== ETL pipeline start ===")
    logger.info("Input directory : %s", input_dir)
    logger.info("Database path   : %s", db_path)

    # --- Ingest ---
    logger.info("[1/4] Ingesting data from %s", input_dir)
    raw_df = ingest_directory(input_dir)
    logger.info("Ingested %d raw rows", len(raw_df))

    # --- Transform ---
    logger.info("[2/4] Transforming data")
    clean_df = transform(raw_df)
    report = transform_field_report(clean_df)
    logger.info("Transform report: %s", report)

    # --- Aggregate ---
    logger.info("[3/4] Aggregating data")
    agg_df = aggregate(clean_df)
    logger.info("Aggregated into %d summary rows", len(agg_df))

    # --- Store ---
    logger.info("[4/4] Writing to database %s", db_path)
    with open_db(db_path) as conn:
        init_schema(conn)
        written = upsert_summary(conn, agg_df)
        total = row_count(conn)
    logger.info("Wrote %d row(s); daily_summary now has %d row(s)", written, total)

    logger.info("=== ETL pipeline complete ===")


def main(argv=None) -> int:
    args = parse_args(argv)

    # Apply log level from CLI flag
    import logging
    logging.getLogger().setLevel(args.log_level)

    try:
        run(args.input_dir, args.db_path)
        return 0
    except Exception:  # noqa: BLE001
        logger.error("Pipeline failed:\n%s", traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
