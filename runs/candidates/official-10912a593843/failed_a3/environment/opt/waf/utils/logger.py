"""
WAF Shared Logging Utilities
Provides structured logging helpers used across all WAF components.
"""

import logging
import json
import sys
import os
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

LOG_DIR = Path("/opt/waf/logs")
DEFAULT_LEVEL = logging.INFO


class StructuredFormatter(logging.Formatter):
    """JSON-structured log formatter for machine parsing."""

    def __init__(self, component: str = "waf"):
        super().__init__()
        self.component = component

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "component": self.component,
            "msg": record.getMessage(),
            "logger": record.name,
        }
        if record.exc_info:
            log_entry["exc"] = self.formatException(record.exc_info)
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if hasattr(record, "rule_id"):
            log_entry["rule_id"] = record.rule_id
        if hasattr(record, "action"):
            log_entry["action"] = record.action
        return json.dumps(log_entry)


class TextFormatter(logging.Formatter):
    """Human-readable log formatter."""

    FMT = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
    DATE_FMT = "%Y-%m-%d %H:%M:%S"

    def __init__(self):
        super().__init__(fmt=self.FMT, datefmt=self.DATE_FMT)


class RateLimitedHandler(logging.Handler):
    """Handler that rate-limits log output to avoid flooding."""

    def __init__(self, inner_handler: logging.Handler, max_per_second: int = 100):
        super().__init__()
        self.inner = inner_handler
        self.max_per_second = max_per_second
        self._count = 0
        self._window_start = time.monotonic()
        self._dropped = 0

    def emit(self, record: logging.LogRecord):
        now = time.monotonic()
        if now - self._window_start >= 1.0:
            if self._dropped > 0:
                drop_record = logging.LogRecord(
                    name=record.name,
                    level=logging.WARNING,
                    pathname="",
                    lineno=0,
                    msg=f"[rate-limited: dropped {self._dropped} messages]",
                    args=(),
                    exc_info=None,
                )
                self.inner.emit(drop_record)
            self._count = 0
            self._dropped = 0
            self._window_start = now

        if self._count < self.max_per_second:
            self.inner.emit(record)
            self._count += 1
        else:
            self._dropped += 1


def setup_logger(
    name: str,
    log_file: Optional[str] = None,
    level: int = DEFAULT_LEVEL,
    structured: bool = False,
    rate_limit: Optional[int] = None,
) -> logging.Logger:
    """Configure and return a logger for a WAF component."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()

    if structured:
        formatter = StructuredFormatter(component=name)
    else:
        formatter = TextFormatter()

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)

    if rate_limit is not None:
        console_handler = RateLimitedHandler(console_handler, max_per_second=rate_limit)

    logger.addHandler(console_handler)

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def log_classification_event(
    logger: logging.Logger,
    request_id: str,
    path: str,
    method: str,
    action: str,
    rule_id: str,
    duration_ms: float,
):
    """Log a structured classification event."""
    extra = {"request_id": request_id, "rule_id": rule_id, "action": action}
    logger.info(
        f"{method} {path} -> {action} (rule={rule_id}, {duration_ms:.2f}ms)",
        extra=extra,
    )


def log_deployment_event(
    logger: logging.Logger,
    rule_count: int,
    hash_value: str,
    deployed_at: str,
):
    """Log a structured deployment event."""
    logger.info(
        f"Rules deployed: count={rule_count}, hash={hash_value[:12]}..., at={deployed_at}"
    )


def get_log_stats(log_file: str) -> dict:
    """Parse a log file and return basic statistics."""
    stats = {"total_lines": 0, "errors": 0, "warnings": 0, "by_level": {}}
    if not os.path.exists(log_file):
        return stats
    try:
        with open(log_file) as f:
            for line in f:
                stats["total_lines"] += 1
                try:
                    entry = json.loads(line)
                    level = entry.get("level", "UNKNOWN")
                except json.JSONDecodeError:
                    if "ERROR" in line:
                        level = "ERROR"
                    elif "WARNING" in line:
                        level = "WARNING"
                    else:
                        level = "INFO"
                stats["by_level"][level] = stats["by_level"].get(level, 0) + 1
                if level == "ERROR":
                    stats["errors"] += 1
                elif level == "WARNING":
                    stats["warnings"] += 1
    except Exception as e:
        stats["error"] = str(e)
    return stats


if __name__ == "__main__":
    test_logger = setup_logger("waf.test", structured=True)
    test_logger.info("Logger utility self-test")
    log_classification_event(
        test_logger,
        request_id="req-001",
        path="/api/v1/users",
        method="GET",
        action="allow",
        rule_id="allow-001",
        duration_ms=0.42,
    )
    print("Logger utility OK")
