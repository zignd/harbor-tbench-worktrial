"""Frontend TSV access-log reader."""

from __future__ import annotations

from pathlib import Path

from .models import FrontendRecord


class AccessLogError(ValueError):
    """Raised when a frontend access log cannot be parsed."""


def parse_tsv(path: Path) -> list[FrontendRecord]:
    records: list[FrontendRecord] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, raw_line in enumerate(stream, 1):
            line = raw_line.rstrip("\n\r")
            if not line:
                continue
            fields = line.split("\t")
            if len(fields) != 6:
                raise AccessLogError(f"{path.name}:{line_number}: expected six columns")
            try:
                timestamp_ms = int(fields[0])
                status = int(fields[4])
                frontend_latency_ms = int(fields[5])
            except ValueError as exc:
                raise AccessLogError(f"{path.name}:{line_number}: invalid integer") from exc
            req_id, client_ip, endpoint = fields[1], fields[2], fields[3]
            if not req_id or not endpoint or frontend_latency_ms <= 0:
                raise AccessLogError(f"{path.name}:{line_number}: invalid record")
            records.append(
                FrontendRecord(
                    timestamp_ms=timestamp_ms,
                    req_id=req_id,
                    client_ip=client_ip,
                    endpoint=endpoint,
                    status=status,
                    frontend_latency_ms=frontend_latency_ms,
                    source=path.name,
                    line_number=line_number,
                )
            )
    return records


def decode_directory(directory: str | Path) -> list[FrontendRecord]:
    root = Path(directory)
    records: list[FrontendRecord] = []
    for path in sorted(root.glob("*.tsv"), key=lambda item: item.name):
        records.extend(parse_tsv(path))
    return records
