"""
WAF Prometheus Metrics Exporter
Exposes rule match counts, classification latency, and deployment status
via a simple HTTP endpoint for Prometheus scraping.
"""

import os
import sys
import json
import time
import threading
import sqlite3
import logging
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from collections import defaultdict

METRICS_PORT = int(os.environ.get("WAF_METRICS_PORT", "9090"))
STATE_DB = "/opt/waf/state.db"
DEPLOYED_DIR = Path("/opt/waf/deployed")

logger = logging.getLogger("waf.metrics")

# In-memory counters
_counters = defaultdict(int)
_latencies = []
_lock = threading.Lock()


def record_classification(action: str, rule_id: str, latency_ms: float) -> None:
    """Record a classification event for metrics."""
    with _lock:
        _counters[f"waf_classifications_total{{action='{action}'}}" ] += 1
        _counters[f"waf_rule_matches_total{{rule='{rule_id}'}}" ] += 1
        _latencies.append(latency_ms)
        if len(_latencies) > 10000:
            _latencies.pop(0)


def get_deployment_info() -> dict:
    """Read deployment metadata from state DB."""
    info = {}
    try:
        conn = sqlite3.connect(STATE_DB)
        rows = conn.execute("SELECT key, value FROM rule_state").fetchall()
        conn.close()
        info = dict(rows)
    except Exception as e:
        logger.error(f"Failed to read state DB: {e}")
    return info


def count_deployed_rules() -> int:
    """Count JSON files in deployed directory."""
    if not DEPLOYED_DIR.exists():
        return 0
    return len(list(DEPLOYED_DIR.glob("*.json")))


def compute_percentile(values: list, pct: float) -> float:
    """Compute a percentile from a list of values."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = int(len(sorted_vals) * pct / 100)
    idx = min(idx, len(sorted_vals) - 1)
    return sorted_vals[idx]


def render_prometheus_metrics() -> str:
    """Render current metrics in Prometheus text format."""
    lines = []
    with _lock:
        counters_snap = dict(_counters)
        latencies_snap = list(_latencies)

    lines.append("# HELP waf_classifications_total Total WAF classifications")
    lines.append("# TYPE waf_classifications_total counter")
    for metric, value in sorted(counters_snap.items()):
        if "classifications" in metric:
            lines.append(f"{metric} {value}")

    lines.append("# HELP waf_rule_matches_total Rule match counts")
    lines.append("# TYPE waf_rule_matches_total counter")
    for metric, value in sorted(counters_snap.items()):
        if "rule_matches" in metric:
            lines.append(f"{metric} {value}")

    lines.append("# HELP waf_deployed_rules_count Number of deployed rules")
    lines.append("# TYPE waf_deployed_rules_count gauge")
    lines.append(f"waf_deployed_rules_count {count_deployed_rules()}")

    if latencies_snap:
        p50 = compute_percentile(latencies_snap, 50)
        p95 = compute_percentile(latencies_snap, 95)
        p99 = compute_percentile(latencies_snap, 99)
        lines.append("# HELP waf_classify_latency_ms Classification latency in ms")
        lines.append("# TYPE waf_classify_latency_ms summary")
        lines.append(f'waf_classify_latency_ms{{quantile="0.5"}} {p50}')
        lines.append(f'waf_classify_latency_ms{{quantile="0.95"}} {p95}')
        lines.append(f'waf_classify_latency_ms{{quantile="0.99"}} {p99}')
        lines.append(f"waf_classify_latency_ms_count {len(latencies_snap)}")
        lines.append(f"waf_classify_latency_ms_sum {sum(latencies_snap):.3f}")

    deploy_info = get_deployment_info()
    if deploy_info.get("rule_count"):
        lines.append("# HELP waf_deployed_rule_count_db Rule count from state DB")
        lines.append("# TYPE waf_deployed_rule_count_db gauge")
        lines.append(f"waf_deployed_rule_count_db {deploy_info['rule_count']}")

    return "\n".join(lines) + "\n"


class MetricsHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler for Prometheus metrics scraping."""

    def do_GET(self):
        if self.path == "/metrics":
            body = render_prometheus_metrics().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/health":
            body = b'{"status": "ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):
        pass  # Suppress default access log


def start_metrics_server(port: int = METRICS_PORT, daemon: bool = True) -> threading.Thread:
    """Start the metrics HTTP server in a background thread."""
    server = HTTPServer(("", port), MetricsHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=daemon)
    thread.start()
    logger.info(f"Metrics server listening on port {port}")
    return thread


def get_metrics_summary() -> dict:
    """Return a dict summary of current metrics."""
    with _lock:
        total = sum(v for k, v in _counters.items() if "classifications" in k)
        blocked = _counters.get("waf_classifications_total{action='block'}", 0)
        allowed = _counters.get("waf_classifications_total{action='allow'}", 0)
        latencies_snap = list(_latencies)

    return {
        "total_classifications": total,
        "blocked": blocked,
        "allowed": allowed,
        "block_rate": blocked / total if total > 0 else 0.0,
        "p50_latency_ms": compute_percentile(latencies_snap, 50),
        "p95_latency_ms": compute_percentile(latencies_snap, 95),
        "deployed_rules": count_deployed_rules(),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(f"Starting WAF metrics exporter on port {METRICS_PORT}")
    t = start_metrics_server(daemon=False)
    t.join()
