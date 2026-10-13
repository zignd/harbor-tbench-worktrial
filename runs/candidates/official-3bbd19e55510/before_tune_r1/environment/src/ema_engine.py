#!/usr/bin/env python3
"""
ema_engine.py - Exponential Moving Average computation engine

Reads binary-packed sample records produced by ingest and computes
EMA statistics for one or more channels.  Results are written to
/app/output/metrics_summary.json.

Binary record layout (48 bytes each, after 8-byte magic header):
  double timestamp  (8 bytes, offset 0)
  double value      (8 bytes, offset 8)
  char[32] channel  (32 bytes, offset 16)

Configuration is read from /app/config/channels.conf which has lines of
the form:   channel_name  window_size

Usage:
  python3 ema_engine.py [--channels ch1,ch2,...] [--packed-dir DIR]
                        [--output PATH] [--verbose]
"""

import argparse
import json
import math
import os
import struct
import sys
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PACKED_DIR      = "/app/data/packed"
CONFIG_PATH     = "/app/config/channels.conf"
OUTPUT_PATH     = "/app/output/metrics_summary.json"
MAGIC           = b"INGST1.0"
RECORD_SIZE     = 48
RECORD_FMT      = "dd32s"   # timestamp(d) value(d) channel(32s)
HEADER_SIZE     = 8
ENGINE_VERSION  = "2.1.0"

# ---------------------------------------------------------------------------
# Configuration loader
# ---------------------------------------------------------------------------

def load_channel_config(config_path: str) -> Dict[str, int]:
    """
    Parse channels.conf and return a dict mapping channel name -> window size.
    Lines starting with '#' or blank are ignored.
    Expected format per line: <channel_name>  <window_size>
    """
    channels: Dict[str, int] = {}
    try:
        with open(config_path, "r") as fh:
            for lineno, raw in enumerate(fh, 1):
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) < 2:
                    sys.stderr.write(
                        f"[ema_engine] WARNING: channels.conf line {lineno} "
                        f"malformed, skipping: {raw!r}\n"
                    )
                    continue
                name   = parts[0]
                try:
                    window = int(parts[1])
                except ValueError:
                    sys.stderr.write(
                        f"[ema_engine] WARNING: bad window size on line {lineno}: "
                        f"{parts[1]!r}, skipping\n"
                    )
                    continue
                if window < 2:
                    sys.stderr.write(
                        f"[ema_engine] WARNING: window size {window} for channel "
                        f"'{name}' is < 2, clamping to 2\n"
                    )
                    window = 2
                channels[name] = window
    except FileNotFoundError:
        sys.stderr.write(f"[ema_engine] ERROR: config file not found: {config_path}\n")
        sys.exit(1)
    return channels

# ---------------------------------------------------------------------------
# Binary packed-file reader
# ---------------------------------------------------------------------------

def read_packed_file(path: str) -> List[Tuple[float, float, str]]:
    """
    Read a .bin file produced by ingest and return a list of
    (timestamp, value, channel_name) tuples in file order.
    """
    records: List[Tuple[float, float, str]] = []
    try:
        with open(path, "rb") as fh:
            magic = fh.read(HEADER_SIZE)
            if magic != MAGIC:
                sys.stderr.write(
                    f"[ema_engine] WARNING: {path} has unexpected magic "
                    f"{magic!r}, proceeding anyway\n"
                )
            raw = fh.read()
        n = len(raw) // RECORD_SIZE
        offset = 0
        for _ in range(n):
            chunk = raw[offset: offset + RECORD_SIZE]
            ts, val, ch_bytes = struct.unpack_from(RECORD_FMT, chunk)
            channel = ch_bytes.rstrip(b"\x00").decode("utf-8", errors="replace")
            records.append((ts, val, channel))
            offset += RECORD_SIZE
    except FileNotFoundError:
        sys.stderr.write(f"[ema_engine] WARNING: packed file not found: {path}\n")
    except Exception as exc:
        sys.stderr.write(f"[ema_engine] ERROR reading {path}: {exc}\n")
    return records

# ---------------------------------------------------------------------------
# EMA computation
# ---------------------------------------------------------------------------

def compute_ema(values: List[float], window_size: int) -> Tuple[float, int]:
    """
    Compute EMA over a sequence of values using the standard recurrence:
      EMA_0  = initial_value   (implementation detail: see below)
      EMA_n  = alpha * x_n + (1 - alpha) * EMA_{n-1}
      alpha  = 2.0 / (window_size - 1)   # smoothing factor

    Returns (final_ema, sample_count).
    """
    if not values:
        return (0.0, 0)

    n = len(values)

    # Smoothing factor derived from the window size
    alpha = 2.0 / (window_size - 1)

    # Initialise EMA at zero; first sample will pull it toward the true signal
    ema = 0.0

    for x in values:
        ema = alpha * x + (1.0 - alpha) * ema

    return (ema, n)


def compute_ema_stats(channel: str, window_size: int,
                       packed_dir: str) -> Optional[Dict]:
    """
    Load packed binary data for a single channel and compute its EMA.
    Returns a dict with keys 'ema' and 'count', or None on failure.
    """
    bin_path = os.path.join(packed_dir, f"{channel}.bin")
    records  = read_packed_file(bin_path)

    if not records:
        sys.stderr.write(
            f"[ema_engine] WARNING: no records found for channel '{channel}'\n"
        )
        return None

    # Extract values in timestamp order (ingest writes them in order, but sort
    # defensively for robustness)
    records.sort(key=lambda r: r[0])
    values = [r[1] for r in records]

    ema_val, count = compute_ema(values, window_size)

    return {
        "ema":   round(ema_val, 8),
        "count": count,
    }

# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_result(result: Dict, channel: str, window: int) -> bool:
    """Basic sanity checks on a computed result."""
    if "ema" not in result or "count" not in result:
        sys.stderr.write(f"[ema_engine] ERROR: missing keys in result for {channel}\n")
        return False
    if result["count"] <= 0:
        sys.stderr.write(f"[ema_engine] WARNING: zero-count result for {channel}\n")
        return False
    if math.isnan(result["ema"]) or math.isinf(result["ema"]):
        sys.stderr.write(f"[ema_engine] ERROR: non-finite EMA for {channel}\n")
        return False
    return True

# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def write_output(results: Dict[str, Dict], output_path: str) -> None:
    """Serialise results to JSON, creating parent directories as needed."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as fh:
        json.dump(results, fh, indent=2)
        fh.write("\n")
    sys.stdout.write(
        f"[ema_engine] wrote {len(results)} channel(s) to {output_path}\n"
    )
    sys.stdout.flush()

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="EMA computation engine for sensor metrics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--channels", default=None,
        help="Comma-separated list of channels to process (default: all from config)",
    )
    p.add_argument(
        "--packed-dir", default=PACKED_DIR,
        help=f"Directory containing .bin files (default: {PACKED_DIR})",
    )
    p.add_argument(
        "--output", default=OUTPUT_PATH,
        help=f"Output JSON path (default: {OUTPUT_PATH})",
    )
    p.add_argument(
        "--config", default=CONFIG_PATH,
        help=f"Channel config file (default: {CONFIG_PATH})",
    )
    p.add_argument(
        "--verbose", action="store_true",
        help="Print per-channel details",
    )
    return p.parse_args()

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    args = parse_args()

    t_start = time.monotonic()

    # Load channel configuration
    all_channels = load_channel_config(args.config)
    if not all_channels:
        sys.stderr.write("[ema_engine] ERROR: no channels loaded from config\n")
        return 1

    # Filter to requested channels
    if args.channels:
        requested = [c.strip() for c in args.channels.split(",")]
        channels = {c: all_channels[c] for c in requested if c in all_channels}
        missing = [c for c in requested if c not in all_channels]
        if missing:
            sys.stderr.write(
                f"[ema_engine] WARNING: channels not in config: {missing}\n"
            )
    else:
        channels = all_channels

    if not channels:
        sys.stderr.write("[ema_engine] ERROR: no channels to process\n")
        return 1

    results: Dict[str, Dict] = {}
    errors = 0

    for ch_name, window in channels.items():
        if args.verbose:
            sys.stdout.write(
                f"[ema_engine] processing channel='{ch_name}' window={window}\n"
            )
            sys.stdout.flush()

        result = compute_ema_stats(ch_name, window, args.packed_dir)
        if result is None:
            errors += 1
            continue

        if not validate_result(result, ch_name, window):
            errors += 1
            continue

        results[ch_name] = result

        if args.verbose:
            sys.stdout.write(
                f"[ema_engine]   ema={result['ema']:.6f}  count={result['count']}\n"
            )

    if not results:
        sys.stderr.write("[ema_engine] ERROR: no valid results to write\n")
        return 1

    write_output(results, args.output)

    t_elapsed = time.monotonic() - t_start
    sys.stdout.write(
        f"[ema_engine] done in {t_elapsed:.3f}s  channels={len(results)}  "
        f"errors={errors}\n"
    )
    sys.stdout.flush()

    return 0 if errors == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
