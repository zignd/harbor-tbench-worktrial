#!/usr/bin/env python3
"""
Log Ingestor

Reads raw JSONL log files from /data/logs/, normalizes them, and writes
metric records to /data/processed/metrics.sqlite.

Each log line is a JSON object with fields:
  service   - service name string
  metric    - metric name string
  ts        - Unix timestamp (float seconds since epoch)
  value     - numeric metric value
  host      - (optional) hostname
  level     - (optional) log level

The ingestor tracks which files have been processed via the ingest_log
table to avoid re-processing. Run with --force to re-ingest all files.

Usage:
  python3 ingestor.py [--db PATH] [--logs-dir PATH] [--force] [--verbose]
"""

import argparse
import glob
import json
import logging
import math
import os
import sqlite3
import sys
import time
from pathlib import Path

DEFAULT_DB = '/data/processed/metrics.sqlite'
DEFAULT_LOGS_DIR = '/data/logs'
SCHEMA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'schema.sql')

REQUIRED_FIELDS = {'service', 'metric', 'ts', 'value'}

log = logging.getLogger('ingestor')


def init_db(db_path):
    """Initialize the SQLite database with the schema."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    if os.path.exists(SCHEMA_FILE):
        with open(SCHEMA_FILE) as f:
            conn.executescript(f.read())
    else:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS raw_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service TEXT NOT NULL,
                metric TEXT NOT NULL,
                ts REAL NOT NULL,
                value REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_raw_metrics_service_metric_ts
                ON raw_metrics(service, metric, ts);
            CREATE TABLE IF NOT EXISTS service_registry (
                service TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                first_seen REAL,
                last_seen REAL
            );
            CREATE TABLE IF NOT EXISTS ingest_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                ingested_at REAL NOT NULL,
                rows_inserted INTEGER NOT NULL
            );
        """)
    conn.commit()
    return conn


def get_ingested_files(conn):
    """Return set of already-ingested filenames."""
    cur = conn.execute('SELECT filename FROM ingest_log')
    return {row[0] for row in cur.fetchall()}


def normalize_record(raw):
    """
    Normalize a raw log record dict.

    Returns a tuple (service, metric, ts, value) or None if invalid.
    Timestamps are stored as float seconds since epoch.
    """
    try:
        missing = REQUIRED_FIELDS - set(raw.keys())
        if missing:
            return None
        service = str(raw['service']).strip().lower()
        metric = str(raw['metric']).strip().lower()
        ts = float(raw['ts'])
        value = float(raw['value'])
        if not service or not metric:
            return None
        if not math.isfinite(ts) or not math.isfinite(value):
            return None
        if ts < 0 or ts > 4e9:
            return None
        return (service, metric, ts, value)
    except (KeyError, ValueError, TypeError):
        return None


def ingest_file(conn, filepath, verbose=False):
    """
    Ingest a single JSONL file into the database.

    Returns the number of rows inserted.
    """
    filename = os.path.basename(filepath)
    rows = []
    services_seen = {}
    errors = 0

    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    errors += 1
                    continue
                record = normalize_record(raw)
                if record is None:
                    errors += 1
                    continue
                service, metric, ts, value = record
                rows.append((service, metric, ts, value))
                if service not in services_seen:
                    services_seen[service] = {'first': ts, 'last': ts, 'display': raw.get('service', service)}
                else:
                    if ts < services_seen[service]['first']:
                        services_seen[service]['first'] = ts
                    if ts > services_seen[service]['last']:
                        services_seen[service]['last'] = ts
    except OSError as e:
        log.error(f"Failed to open {filepath}: {e}")
        return 0

    if verbose:
        log.info(f"{filename}: {len(rows)} valid records, {errors} errors")

    if not rows:
        conn.execute(
            'INSERT INTO ingest_log (filename, ingested_at, rows_inserted) VALUES (?, ?, ?)',
            (filename, time.time(), 0)
        )
        conn.commit()
        return 0

    conn.executemany(
        'INSERT INTO raw_metrics (service, metric, ts, value) VALUES (?, ?, ?, ?)',
        rows
    )

    now = time.time()
    for service, info in services_seen.items():
        conn.execute("""
            INSERT INTO service_registry (service, display_name, first_seen, last_seen)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(service) DO UPDATE SET
                display_name = excluded.display_name,
                first_seen = MIN(first_seen, excluded.first_seen),
                last_seen = MAX(last_seen, excluded.last_seen)
        """, (service, info['display'], info['first'], info['last']))

    conn.execute(
        'INSERT INTO ingest_log (filename, ingested_at, rows_inserted) VALUES (?, ?, ?)',
        (filename, now, len(rows))
    )
    conn.commit()
    return len(rows)


def run_ingestor(db_path, logs_dir, force=False, verbose=False):
    """Main ingestor loop."""
    conn = init_db(db_path)
    ingested = set() if force else get_ingested_files(conn)

    pattern = os.path.join(logs_dir, '*.jsonl')
    files = sorted(glob.glob(pattern))

    if not files:
        log.warning(f"No .jsonl files found in {logs_dir}")
        conn.close()
        return

    total_rows = 0
    for filepath in files:
        filename = os.path.basename(filepath)
        if filename in ingested:
            if verbose:
                log.debug(f"Skipping already-ingested: {filename}")
            continue
        rows = ingest_file(conn, filepath, verbose=verbose)
        total_rows += rows
        log.info(f"Ingested {filename}: {rows} rows")

    log.info(f"Total rows inserted: {total_rows}")
    conn.close()


def main():
    parser = argparse.ArgumentParser(description='Log ingestor for metrics pipeline')
    parser.add_argument('--db', default=DEFAULT_DB, help='SQLite database path')
    parser.add_argument('--logs-dir', default=DEFAULT_LOGS_DIR, help='Directory containing .jsonl log files')
    parser.add_argument('--force', action='store_true', help='Re-ingest all files even if already processed')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format='%(asctime)s %(levelname)s %(name)s: %(message)s')

    run_ingestor(args.db, args.logs_dir, force=args.force, verbose=args.verbose)


if __name__ == '__main__':
    main()
