"""
WAF Shared Logger Utility
Provides structured logging helpers used across all WAF components.
"""

import os
import sys
import json
import logging
import logging.handlers
import time
import threading
from pathlib import Path
from datetime import datetime, timezone

LOG_DIR = Path("/opt/waf/logs")
DEFAULT_LEVEL = os.environ.get("WAF_LOG_LEVEL", "INFO")
MAX_BYTES = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5

_loggers = {}
_lock = threading.Lock()


class StructuredFormatter(logging.Formatter):
    """JSON-structured log formatter for machine-readable output."""

    def __init__(self, component: str):
        super().__init__()
        self.component = component

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "component": self.component,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        if hasattr(record, "request_id"):
            entry["request_id"] = record.request_id
        if hasattr(record, "rule_id"):
            entry["rule_id"] = record.rule_id
        return json.dumps(entry)


class RateLimitedHandler(logging.Handler):
    """
    A handler that rate-limits log output to avoid flooding.
    Drops records beyond max_per_second in any given second.
    """

    def __init__(self, inner: logging.Handler, max_per_second: int = 100):
        super().__init__()
        self.inner = inner
        self.max_per_second = max_per_second
        self._bucket_time = 0
        self._bucket_count = 0
        self._dropped = 0
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        now = int(time.time())
        with self._lock:
            if now != self._bucket_time:
                if self._dropped > 0:
                    drop_record = logging.LogRecord(
                        name=record.name,
                        level=logging.WARNING,
                        pathname="",
                        lineno=0,
                        msg=f"Rate limiter dropped {self._dropped} log records in second {self._bucket_time}",
                        args=(),
                        exc_info=None,
                    )
                    self.inner.emit(drop_record)
                self._bucket_time = now
                self._bucket_count = 0
                self._dropped = 0

            if self._bucket_count < self.max_per_second:
                self._bucket_count += 1
                self.inner.emit(record)
            else:
                self._dropped += 1


def get_logger(
    component: str,
    log_file: str | None = None,
    level: str | None = None,
    structured: bool = True,
) -> logging.Logger:
    """
    Get (or create) a logger for the given component.
    Uses rotating file handler + stderr handler.
    """
    with _lock:
        if component in _loggers:
            return _loggers[component]

        log_level = getattr(logging, (level or DEFAULT_LEVEL).upper(), logging.INFO)
        logger = logging.getLogger(f"waf.{component}")
        logger.setLevel(log_level)
        logger.propagate = False

        formatter: logging.Formatter
        if structured:
            formatter = StructuredFormatter(component)
        else:
            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            )

        # Stderr handler
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setFormatter(formatter)
        stderr_handler.setLevel(log_level)
        logger.addHandler(RateLimitedHandler(stderr_handler))

        # File handler (rotating)
        if log_file:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=MAX_BYTES,
                backupCount=BACKUP_COUNT,
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(log_level)
            logger.addHandler(file_handler)

        _loggers[component] = logger
        return logger


class RequestContext:
    """Thread-local context for associating log records with a request."""

    _local = threading.local()

    @classmethod
    def set(cls, request_id: str, client_ip: str = "") -> None:
        cls._local.request_id = request_id
        cls._local.client_ip = client_ip

    @classmethod
    def get_request_id(cls) -> str:
        return getattr(cls._local, "request_id", "")

    @classmethod
    def get_client_ip(cls) -> str:
        return getattr(cls._local, "client_ip", "")

    @classmethod
    def clear(cls) -> None:
        cls._local.request_id = ""
        cls._local.client_ip = ""


class TimedOperation:
    """Context manager that logs the duration of a code block."""

    def __init__(self, logger: logging.Logger, operation: str, level: int = logging.DEBUG):
        self.logger = logger
        self.operation = operation
        self.level = level
        self.start_time = 0.0
        self.elapsed_ms = 0.0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.elapsed_ms = (time.perf_counter() - self.start_time) * 1000
        if exc_type is None:
            self.logger.log(
                self.level,
                f"{self.operation} completed in {self.elapsed_ms:.2f}ms",
            )
        else:
            self.logger.error(
                f"{self.operation} failed after {self.elapsed_ms:.2f}ms: {exc_val}"
            )
        return False


def log_classification_event(
    logger: logging.Logger,
    request_path: str,
    action: str,
    rule_id: str,
    latency_ms: float,
) -> None:
    """Log a structured classification event."""
    extra = {
        "request_id": RequestContext.get_request_id(),
        "rule_id": rule_id,
    }
    logger.info(
        f"classify path={request_path!r} action={action} rule={rule_id} "
        f"latency={latency_ms:.2f}ms",
        extra=extra,
    )
