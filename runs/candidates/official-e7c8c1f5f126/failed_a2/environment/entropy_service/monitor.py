"""
monitor.py - Continuous entropy monitoring daemon stub.

Provides a background monitoring loop that periodically ingests new byte
samples from configured hardware RNG sources and updates the entropy audit
log. This module is a stub; the real scheduling backend is out of scope.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

from schema import SourceConfig, SourceAuditResult
from utils import configure_logging, get_logger, Timer

logger = get_logger(__name__)


# ── Monitor configuration ─────────────────────────────────────────────────────

MONITOR_INTERVAL_SECONDS: float = 60.0
MONITOR_MAX_FAILURES: int = 3
MONITOR_BACKOFF_FACTOR: float = 2.0


class SourceMonitorState:
    """Tracks runtime state for a single monitored source."""

    def __init__(self, config: SourceConfig) -> None:
        self.config = config
        self.consecutive_failures: int = 0
        self.last_run_ts: Optional[float] = None
        self.last_result: Optional[SourceAuditResult] = None
        self.total_runs: int = 0
        self.total_failures: int = 0

    @property
    def source_id(self) -> str:
        return self.config.source_id

    def record_success(self, result: SourceAuditResult) -> None:
        self.last_result = result
        self.last_run_ts = time.time()
        self.consecutive_failures = 0
        self.total_runs += 1
        logger.info("Source %s audit OK (mean=%.4f)", self.source_id, result.mean_entropy)

    def record_failure(self, exc: Exception) -> None:
        self.consecutive_failures += 1
        self.total_failures += 1
        self.total_runs += 1
        logger.error(
            "Source %s audit failed (%d consecutive): %s",
            self.source_id, self.consecutive_failures, exc,
        )

    def is_degraded(self) -> bool:
        return self.consecutive_failures >= MONITOR_MAX_FAILURES

    def backoff_interval(self) -> float:
        if self.consecutive_failures == 0:
            return MONITOR_INTERVAL_SECONDS
        factor = MONITOR_BACKOFF_FACTOR ** min(self.consecutive_failures, 5)
        return min(MONITOR_INTERVAL_SECONDS * factor, 3600.0)


# ── Alert dispatcher ─────────────────────────────────────────────────────────

AlertCallback = Callable[[str, str, str], None]


class AlertDispatcher:
    """Routes alerts to registered callback handlers."""

    def __init__(self) -> None:
        self._handlers: List[AlertCallback] = []

    def register(self, handler: AlertCallback) -> None:
        self._handlers.append(handler)

    def dispatch(self, source_id: str, severity: str, message: str) -> None:
        for handler in self._handlers:
            try:
                handler(source_id, severity, message)
            except Exception as e:
                logger.warning("Alert handler error: %s", e)

    def log_handler(self, source_id: str, severity: str, message: str) -> None:
        level = getattr(logging, severity, logging.WARNING)
        logger.log(level, "[%s] %s", source_id, message)


# ── Monitor loop ─────────────────────────────────────────────────────────────

class EntropyMonitor:
    """
    Background monitor that periodically audits entropy sources.

    Usage (stub — real implementation requires a scheduler):

        monitor = EntropyMonitor(configs, audit_fn)
        monitor.run_once()
    """

    def __init__(
        self,
        configs: List[SourceConfig],
        audit_fn: Callable[[SourceConfig], SourceAuditResult],
        alert_dispatcher: Optional[AlertDispatcher] = None,
    ) -> None:
        self._states: Dict[str, SourceMonitorState] = {
            c.source_id: SourceMonitorState(c) for c in configs
        }
        self._audit_fn = audit_fn
        self._dispatcher = alert_dispatcher or AlertDispatcher()
        self._dispatcher.register(self._dispatcher.log_handler)

    def run_once(self) -> Dict[str, Optional[SourceAuditResult]]:
        """Run one audit pass across all configured sources."""
        results: Dict[str, Optional[SourceAuditResult]] = {}
        for source_id, state in self._states.items():
            if not state.config.enabled:
                logger.debug("Skipping disabled source %s", source_id)
                results[source_id] = None
                continue
            with Timer() as t:
                try:
                    result = self._audit_fn(state.config)
                    state.record_success(result)
                    results[source_id] = result
                    self._check_alerts(state, result)
                except Exception as exc:
                    state.record_failure(exc)
                    results[source_id] = None
            logger.debug("Source %s took %s", source_id, t)
        return results

    def _check_alerts(self, state: SourceMonitorState, result: SourceAuditResult) -> None:
        if result.n_degenerate > 0 and state.config.alert_on_degenerate:
            self._dispatcher.dispatch(
                state.source_id,
                "ERROR",
                f"{result.n_degenerate} degenerate windows detected (mean={result.mean_entropy:.4f})",
            )
        if result.min_entropy < state.config.expected_entropy_low:
            self._dispatcher.dispatch(
                state.source_id,
                "WARN",
                f"Min entropy {result.min_entropy:.4f} below threshold {state.config.expected_entropy_low}",
            )

    def status_summary(self) -> str:
        lines = ["=== Monitor Status ==="]
        for sid, state in self._states.items():
            last = "never" if state.last_run_ts is None else time.strftime(
                "%H:%M:%S", time.localtime(state.last_run_ts)
            )
            lines.append(
                f"  {sid}: runs={state.total_runs} failures={state.total_failures} last={last}"
            )
        return "\n".join(lines)


# ── Entrypoint stub ───────────────────────────────────────────────────────────

def start_daemon(config_path: str) -> None:
    """
    Start the monitoring daemon (stub).
    Real implementation would daemonise and loop indefinitely.
    """
    configure_logging()
    logger.info("Entropy monitor daemon starting (stub mode)")
    logger.info("Config: %s", config_path)
    logger.warning("Daemon mode not fully implemented; use audit_runner.py for one-shot runs")


if __name__ == "__main__":
    import sys
    cfg = sys.argv[1] if len(sys.argv) > 1 else "sources.json"
    start_daemon(cfg)
