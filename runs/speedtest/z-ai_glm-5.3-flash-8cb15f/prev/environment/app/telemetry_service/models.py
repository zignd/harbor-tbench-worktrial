"""Immutable records shared by the unpackers, attribution engine, and API."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FrontendRecord:
    timestamp_ms: int
    req_id: str
    client_ip: str
    endpoint: str
    status: int
    frontend_latency_ms: int
    source: str
    line_number: int

    @property
    def end_ms(self) -> int:
        return self.timestamp_ms + self.frontend_latency_ms


@dataclass(frozen=True)
class BackendRecord:
    endpoint: str
    worker_id: int
    exit_code: int
    start_ms: int
    duration_ms: int
    source: str
    record_index: int

    @property
    def end_ms(self) -> int:
        return self.start_ms + self.duration_ms


@dataclass(frozen=True)
class MatchedSession:
    frontend: FrontendRecord
    backend: BackendRecord
    slack_ms: int

    @property
    def backend_latency_ms(self) -> int:
        return self.backend.duration_ms

    @property
    def failed(self) -> bool:
        return self.backend.exit_code != 0
