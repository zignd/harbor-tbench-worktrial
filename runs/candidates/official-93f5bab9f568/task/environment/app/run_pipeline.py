# CLI entry point for the ETL pipeline

import sys
import os
import time
import argparse

# Ensure /app is on the path when run directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DEFAULT_INPUT_DIR, DEFAULT_DB_PATH
from ingest import ingest_pipeline
from transform import transform
from aggregate import aggregate, aggregate_summary
from storage import init_db, write_aggregates, get_row_count, close_db
from utils import get_logger, format_elapsed

logger = get_logger("run_pipeline")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Run the ETL pipeline: ingest CSV files, aggregate, write to SQLite."
    )
    parser.add_argument(
        "input_dir",
        nargs="?",
        default=DEFAULT_INPUT_DIR,
        help="Directory containing input CSV files (default: %(default)s)",
    )
    parser.add_argument(
        "db_path",
        nargs="?",
        default=DEFAULT_DB_PATH,
        help="Path to the output SQLite database (default: %(default)s)",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        help="Override log level (DEBUG, INFO, WARNING, ERROR)",
    )
    return parser.parse_args(argv)


def run(input_dir: str, db_path: str) -> None:
    """Execute the full ETL pipeline."""
    t0 = time.time()
    logger.info(f"Pipeline starting: input_dir={input_dir}, db_path={db_path}")

    # Step 1: Ingest
    raw_df = ingest_pipeline(input_dir)
    if raw_df.empty:
        logger.warning("No data ingested; pipeline exiting early")
        return
    logger.info(f"Ingested {len(raw_df)} raw rows")

    # Step 2: Transform
    clean_df = transform(raw_df)
    if clean_df.empty:
        logger.warning("No data after transform; pipeline exiting early")
        return
    logger.info(f"Transformed to {len(clean_df)} clean rows")

    # Step 3: Aggregate
    agg_df = aggregate(clean_df)
    summary = aggregate_summary(agg_df)
    logger.info(f"Aggregate summary: {summary}")

    # Step 4: Store
    conn = init_db(db_path)
    try:
        rows_written = write_aggregates(conn, agg_df)
        total_rows = get_row_count(conn)
        logger.info(f"Rows written this run: {rows_written}")
        logger.info(f"Total rows in daily_summary: {total_rows}")
    finally:
        close_db(conn)

    elapsed = time.time() - t0
    logger.info(f"Pipeline complete in {format_elapsed(elapsed)}")


def main(argv=None):
    args = parse_args(argv)

    if args.log_level:
        import logging
        level = getattr(logging, args.log_level.upper(), logging.INFO)
        logging.getLogger().setLevel(level)

    try:
        run(args.input_dir, args.db_path)
    except Exception as exc:
        logger.error(f"Pipeline failed: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
