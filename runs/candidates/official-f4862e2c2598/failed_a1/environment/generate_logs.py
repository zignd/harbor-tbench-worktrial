#!/usr/bin/env python3
"""
Deterministic log generator for the metrics pipeline.

Generates 30 days of realistic JSONL log data across 8 microservices.
Output goes to /data/logs/ as one file per service per day.

This script was used during environment setup and is kept here for reference.
The generated data is already present in /data/logs/.

Usage:
  python3 generate_logs.py [--output-dir DIR] [--seed INT] [--days INT]
"""

import argparse
import json
import math
import os
import random
import time
from datetime import datetime, timezone

DEFAULT_OUTPUT_DIR = '/data/logs'
DEFAULT_SEED = 42
DEFAULT_DAYS = 30

SERVICES = [
    {'name': 'auth', 'display': 'Auth Service',
     'metrics': ['login_latency_ms', 'token_validation_ms', 'failed_logins'],
     'base_rate': 120, 'burst_factor': 4.0},
    {'name': 'api-gateway', 'display': 'API Gateway',
     'metrics': ['request_latency_ms', 'upstream_latency_ms', 'error_rate'],
     'base_rate': 300, 'burst_factor': 6.0},
    {'name': 'worker', 'display': 'Background Worker',
     'metrics': ['job_duration_ms', 'queue_depth', 'failed_jobs'],
     'base_rate': 60, 'burst_factor': 3.0},
    {'name': 'cache', 'display': 'Cache Service',
     'metrics': ['hit_rate', 'miss_rate', 'eviction_count'],
     'base_rate': 200, 'burst_factor': 2.0},
    {'name': 'db-proxy', 'display': 'Database Proxy',
     'metrics': ['query_latency_ms', 'connection_pool_used', 'slow_queries'],
     'base_rate': 150, 'burst_factor': 3.5},
    {'name': 'mailer', 'display': 'Mail Service',
     'metrics': ['send_latency_ms', 'delivery_failures', 'queue_size'],
     'base_rate': 15, 'burst_factor': 5.0},
    {'name': 'scheduler', 'display': 'Job Scheduler',
     'metrics': ['schedule_latency_ms', 'missed_jobs', 'active_jobs'],
     'base_rate': 8, 'burst_factor': 2.0},
    {'name': 'billing', 'display': 'Billing Service',
     'metrics': ['charge_latency_ms', 'refund_latency_ms', 'failed_charges'],
     'base_rate': 25, 'burst_factor': 3.0},
]

HOSTS = ['host-{:02d}'.format(i) for i in range(1, 9)]
LEVELS = ['INFO', 'INFO', 'INFO', 'WARN', 'ERROR']


def generate_value(metric, rng, hour_of_day):
    """Generate a realistic metric value based on metric name and time of day."""
    # Business hours pattern: higher traffic 8am-8pm
    hour_factor = 1.0 + 1.5 * math.exp(-0.5 * ((hour_of_day - 14) / 5) ** 2)

    if 'latency' in metric:
        base = rng.lognormvariate(3.5, 0.6)  # ~33ms median
        return round(base * hour_factor, 3)
    elif 'rate' in metric and 'hit' in metric:
        return round(min(0.99, max(0.5, rng.gauss(0.82, 0.08))), 4)
    elif 'rate' in metric:
        return round(max(0.0, rng.gauss(0.02, 0.01)), 4)
    elif 'count' in metric or 'depth' in metric or 'size' in metric:
        return max(0, int(rng.expovariate(0.1) * hour_factor))
    elif 'failed' in metric or 'miss' in metric or 'slow' in metric:
        return max(0, int(rng.expovariate(1.0)))
    elif 'pool_used' in metric:
        return max(1, min(100, int(rng.gauss(40, 15))))
    elif 'active' in metric:
        return max(0, int(rng.gauss(5, 2)))
    else:
        return round(max(0.0, rng.lognormvariate(2.0, 0.5)), 3)


def poisson_times(rng, rate_per_minute, duration_secs):
    """Generate Poisson-distributed event times."""
    times = []
    t = 0.0
    rate_per_sec = rate_per_minute / 60.0
    while t < duration_secs:
        if rate_per_sec > 0:
            t += rng.expovariate(rate_per_sec)
        else:
            break
        if t < duration_secs:
            times.append(t)
    return times


def generate_day(service, day_start_ts, rng, output_dir):
    """
    Generate one day of log data for a service.
    Writes to output_dir/{service}_{date}.jsonl
    """
    date_str = datetime.fromtimestamp(day_start_ts, tz=timezone.utc).strftime('%Y%m%d')
    filename = f"{service['name']}_{date_str}.jsonl"
    filepath = os.path.join(output_dir, filename)

    records = []
    SECS_PER_DAY = 86400

    for metric in service['metrics']:
        # Vary rate by hour with bursts
        for hour in range(24):
            hour_start = hour * 3600
            hour_of_day = hour

            # Base rate with daily pattern
            business_hour = 8 <= hour < 20
            rate_mult = 2.0 if business_hour else 0.4

            # Occasional bursts
            if rng.random() < 0.15:
                rate_mult *= service['burst_factor']

            rate = service['base_rate'] * rate_mult
            times = poisson_times(rng, rate, 3600)

            for t_offset in times:
                ts = day_start_ts + hour_start + t_offset
                value = generate_value(metric, rng, hour_of_day)
                host = rng.choice(HOSTS)
                level = rng.choice(LEVELS)
                records.append({
                    'service': service['name'],
                    'metric': metric,
                    'ts': round(ts, 3),
                    'value': value,
                    'host': host,
                    'level': level,
                })

    # Sort by timestamp
    records.sort(key=lambda r: r['ts'])

    with open(filepath, 'w') as f:
        for rec in records:
            f.write(json.dumps(rec) + '\n')

    return len(records)


def main():
    parser = argparse.ArgumentParser(description='Generate synthetic log data')
    parser.add_argument('--output-dir', default=DEFAULT_OUTPUT_DIR)
    parser.add_argument('--seed', type=int, default=DEFAULT_SEED)
    parser.add_argument('--days', type=int, default=DEFAULT_DAYS)
    parser.add_argument('--end-ts', type=float, default=None,
                        help='End timestamp (default: now rounded to day)')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    rng = random.Random(args.seed)

    if args.end_ts is not None:
        end_ts = args.end_ts
    else:
        # Use a fixed reference time for determinism: 2024-01-31 00:00:00 UTC
        end_ts = 1706659200.0

    # Round end_ts down to midnight UTC
    end_day = int(end_ts // 86400) * 86400
    start_day = end_day - args.days * 86400

    total_records = 0
    for day_offset in range(args.days):
        day_start = start_day + day_offset * 86400
        for service in SERVICES:
            # Use a deterministic per-service-per-day seed
            day_rng = random.Random(args.seed ^ (day_offset * 31337) ^ hash(service['name']))
            n = generate_day(service, day_start, day_rng, args.output_dir)
            total_records += n

    print(f"Generated {total_records} records across {args.days} days for {len(SERVICES)} services")
    print(f"Output: {args.output_dir}")


if __name__ == '__main__':
    main()
