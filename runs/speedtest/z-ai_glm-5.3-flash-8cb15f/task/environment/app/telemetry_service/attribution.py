"""Temporal matching between frontend requests and backend executions."""

from __future__ import annotations

from dataclasses import dataclass

from .models import BackendRecord, FrontendRecord, MatchedSession


@dataclass(frozen=True)
class AttributionResult:
    sessions: tuple[MatchedSession, ...]
    frontend_count: int
    backend_count: int


def attribute(frontend: list[FrontendRecord], backend: list[BackendRecord]) -> AttributionResult:
    """Allocate frontend requests to backend executions."""

    by_endpoint: dict[str, list[BackendRecord]] = {}
    for record in backend:
        by_endpoint.setdefault(record.endpoint, []).append(record)

    sessions: list[MatchedSession] = []
    used_backend: set[int] = set()
    for frontend in frontend:
        candidates = []
        for backend_record in by_endpoint.get(frontend.endpoint, ()):
            if (
                backend_record.start_ms > frontend.timestamp_ms
                and backend_record.end_ms < frontend.end_ms
            ):
                slack = (
                    backend_record.start_ms
                    - frontend.timestamp_ms
                    + frontend.end_ms
                    - backend_record.end_ms
                )
                candidates.append((slack, backend_record))
        if not candidates:
            continue
        candidates.sort(key=lambda item: (item[0], item[1].start_ms, item[1].record_index))
        for slack, backend_record in candidates:
            if id(backend_record) in used_backend:
                continue
            used_backend.add(id(backend_record))
            sessions.append(MatchedSession(frontend, backend_record, slack))
            break

    return AttributionResult(
        sessions=tuple(sessions),
        frontend_count=len(frontend),
        backend_count=len(backend),
    )
