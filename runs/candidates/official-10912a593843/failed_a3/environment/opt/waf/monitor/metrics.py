"""
WAF Prometheus Metrics Exporter
Exposes rule match counts and filter latency for monitoring.
"""

import time
import json
import sqlite3
import threading
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta

METRICS_PORT = 9101
STATE_DB = "/opt/waf/state.db"
DEPLOYED_DIR = Path("/opt/waf/deployed")
METRICS_FILE = "/opt/waf/monitor/metrics.prom"

_counters = defaultdict(int)
_latencies = []
_lock = threading.Lock()


class Counter:
    def __init__(self, name: str, help_text: str, labels: list = None):
        self.name = name
        self.help_text = help_text
        self.labels = labels or []
        self._values = defaultdict(int)

    def inc(self, label_values: dict = None, amount: int = 1):
        key = tuple(sorted((label_values or {}).items()))
        with _lock:
            self._values[key] += amount

    def collect(self) -> list:
        lines = []
        lines.append(f"# HELP {self.name} {self.help_text}")
        lines.append(f"# TYPE {self.name} counter")
        with _lock:
            for key, val in self._values.items():
                if key:
                    label_str = ",".join(f'{k}="{v}"' for k, v in key)
                    lines.append(f"{self.name}{{{label_str}}} {val}")
                else:
                    lines.append(f"{self.name} {val}")
        return lines


class Histogram:
    def __init__(self, name: str, help_text: str, buckets: list = None):
        self.name = name
        self.help_text = help_text
        self.buckets = buckets or [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
        self._observations = []

    def observe(self, value: float):
        with _lock:
            self._observations.append(value)

    def collect(self) -> list:
        lines = []
        lines.append(f"# HELP {self.name} {self.help_text}")
        lines.append(f"# TYPE {self.name} histogram")
        with _lock:
            obs = list(self._observations)
        total = sum(obs)
        count = len(obs)
        for b in self.buckets:
            bucket_count = sum(1 for o in obs if o <= b)
            lines.append(f"{self.name}_bucket{{le=\"{b}\"}} {bucket_count}")
        lines.append(f"{self.name}_bucket{{le=\"+Inf\"}} {count}")
        lines.append(f"{self.name}_sum {total}")
        lines.append(f"{self.name}_count {count}")
        return lines


class Gauge:
    def __init__(self, name: str, help_text: str):
        self.name = name
        self.help_text = help_text
        self._value = 0.0

    def set(self, value: float):
        with _lock:
            self._value = value

    def collect(self) -> list:
        lines = []
        lines.append(f"# HELP {self.name} {self.help_text}")
        lines.append(f"# TYPE {self.name} gauge")
        with _lock:
            lines.append(f"{self.name} {self._value}")
        return lines


requests_total = Counter(
    "waf_requests_total",
    "Total WAF classified requests",
    ["action"],
)
classify_duration = Histogram(
    "waf_classify_duration_seconds",
    "Time spent classifying a request",
)
rules_loaded = Gauge(
    "waf_rules_loaded",
    "Number of rules currently loaded",
)
deployment_age_seconds = Gauge(
    "waf_deployment_age_seconds",
    "Seconds since last rule deployment",
)


def record_classification(action: str, duration_seconds: float):
    requests_total.inc({"action": action})
    classify_duration.observe(duration_seconds)


def update_rule_metrics():
    count = len(list(DEPLOYED_DIR.glob("*.json"))) if DEPLOYED_DIR.exists() else 0
    rules_loaded.set(float(count))

    try:
        conn = sqlite3.connect(STATE_DB)
        row = conn.execute(
            "SELECT value FROM rule_state WHERE key = 'deployed_at'"
        ).fetchone()
        conn.close()
        if row:
            deployed_at = datetime.fromisoformat(row[0])
            age = (datetime.utcnow() - deployed_at).total_seconds()
            deployment_age_seconds.set(age)
    except Exception:
        pass


def render_metrics() -> str:
    update_rule_metrics()
    collectors = [requests_total, classify_duration, rules_loaded, deployment_age_seconds]
    lines = []
    for collector in collectors:
        lines.extend(collector.collect())
    lines.append("")
    return "\n".join(lines)


def write_metrics_file():
    content = render_metrics()
    tmp = METRICS_FILE + ".tmp"
    with open(tmp, "w") as f:
        f.write(content)
    import os
    os.replace(tmp, METRICS_FILE)


def get_summary() -> dict:
    with _lock:
        actions = dict(requests_total._values)
        obs = list(classify_duration._observations)
    return {
        "total_requests": sum(actions.values()),
        "by_action": {str(k): v for k, v in actions.items()},
        "avg_latency_ms": (sum(obs) / len(obs) * 1000) if obs else 0,
        "p99_latency_ms": (sorted(obs)[int(len(obs) * 0.99)] * 1000) if obs else 0,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="WAF Metrics Exporter")
    parser.add_argument("--once", action="store_true", help="Write metrics once and exit")
    parser.add_argument("--output", default=METRICS_FILE)
    args = parser.parse_args()

    METRICS_FILE = args.output

    if args.once:
        write_metrics_file()
        print(f"Metrics written to {METRICS_FILE}")
    else:
        print(f"Metrics exporter running, writing to {METRICS_FILE} every 15s")
        while True:
            write_metrics_file()
            time.sleep(15)
