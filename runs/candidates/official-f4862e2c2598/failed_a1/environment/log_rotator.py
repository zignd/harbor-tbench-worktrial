#!/usr/bin/env python3
"""
Log Rotator

Periodically rotates log files and triggers the ingestor to process new data.
Runs as a background daemon; can also be invoked directly for a single rotation.

Behavior:
- Checks /data/logs/ for files older than MAX_AGE_SECONDS
- Rotates files by renaming them with a timestamp suffix
- Triggers ingestor.py to process any new files
- Keeps at most MAX_FILES rotated files per service (deletes oldest)

Usage:
  python3 log_rotator.py [--interval SECONDS] [--once] [--verbose]
"""

import argparse
import glob
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_LOGS_DIR = '/data/logs'
DEFAULT_PROCESSED_DIR = '/data/processed'
DEFAULT_DB = '/data/processed/metrics.sqlite'
ROTATOR_INTERVAL = 300  # seconds between rotation checks
MAX_AGE_SECONDS = 3600  # rotate files older than this
MAX_FILES = 72          # keep at most this many rotated files

log = logging.getLogger('log_rotator')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INGESTOR_PATH = os.path.join(SCRIPT_DIR, 'ingestor.py')


def rotate_logs(logs_dir, max_age=MAX_AGE_SECONDS, max_files=MAX_FILES, verbose=False):
    """
    Rotate log files older than max_age seconds.
    Returns list of rotated filenames.
    """
    now = time.time()
    rotated = []
    pattern = os.path.join(logs_dir, '*.jsonl')

    for filepath in glob.glob(pattern):
        # Skip already-rotated files (contain a dot besides the extension)
        basename = os.path.basename(filepath)
        if basename.count('.') > 1:
            continue

        try:
            mtime = os.path.getmtime(filepath)
            age = now - mtime
            if age >= max_age:
                ts_suffix = time.strftime('%Y%m%d_%H%M%S', time.gmtime(mtime))
                new_name = filepath.replace('.jsonl', f'.{ts_suffix}.jsonl')
                os.rename(filepath, new_name)
                rotated.append(new_name)
                if verbose:
                    log.info(f"Rotated {basename} -> {os.path.basename(new_name)}")
        except OSError as e:
            log.warning(f"Failed to rotate {filepath}: {e}")

    # Prune old rotated files
    rotated_files = sorted(glob.glob(os.path.join(logs_dir, '*.*.jsonl')))
    if len(rotated_files) > max_files:
        to_delete = rotated_files[:len(rotated_files) - max_files]
        for f in to_delete:
            try:
                os.unlink(f)
                if verbose:
                    log.info(f"Pruned old file: {os.path.basename(f)}")
            except OSError:
                pass

    return rotated


def run_ingestor(db_path, logs_dir, verbose=False):
    """Invoke ingestor.py as a subprocess."""
    cmd = [
        sys.executable, INGESTOR_PATH,
        '--db', db_path,
        '--logs-dir', logs_dir,
    ]
    if verbose:
        cmd.append('--verbose')
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            log.error(f"Ingestor failed: {result.stderr}")
        elif verbose:
            log.info(f"Ingestor output: {result.stdout.strip()}")
    except subprocess.TimeoutExpired:
        log.error("Ingestor timed out")
    except Exception as e:
        log.error(f"Failed to run ingestor: {e}")


def main():
    parser = argparse.ArgumentParser(description='Log rotator for metrics pipeline')
    parser.add_argument('--interval', type=float, default=ROTATOR_INTERVAL,
                        help='Seconds between rotation checks (daemon mode)')
    parser.add_argument('--once', action='store_true',
                        help='Run one rotation cycle and exit')
    parser.add_argument('--db', default=DEFAULT_DB, help='SQLite database path')
    parser.add_argument('--logs-dir', default=DEFAULT_LOGS_DIR,
                        help='Directory containing log files')
    parser.add_argument('--max-age', type=float, default=MAX_AGE_SECONDS,
                        help='Rotate files older than this many seconds')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format='%(asctime)s %(levelname)s %(name)s: %(message)s')

    os.makedirs(args.logs_dir, exist_ok=True)
    os.makedirs(os.path.dirname(args.db), exist_ok=True)

    while True:
        log.info("Running rotation cycle")
        rotated = rotate_logs(args.logs_dir, max_age=args.max_age, verbose=args.verbose)
        if rotated:
            log.info(f"Rotated {len(rotated)} file(s); running ingestor")
            run_ingestor(args.db, args.logs_dir, verbose=args.verbose)
        else:
            log.info("No files rotated; running ingestor for any new files")
            run_ingestor(args.db, args.logs_dir, verbose=args.verbose)

        if args.once:
            break
        log.info(f"Sleeping {args.interval}s until next cycle")
        time.sleep(args.interval)


if __name__ == '__main__':
    main()
