#!/usr/bin/env python3
"""Generate deterministic legacy frontend and backend telemetry samples."""

from __future__ import annotations

import argparse
import os
import random
import struct
from pathlib import Path

BASE_TIMESTAMP_MS = 1_700_000_000_000 + 3_600_000
SPAN_MS = 3 * 60 * 60 * 1000
DEFAULT_ENDPOINTS = (
    "/api/ingest",
    "/api/profile",
    "/api/search",
    "/api/export",
    "/api/replay",
    "/api/annotate",
)
FRONTEND_ONLY_ENDPOINTS = (
    "/health/internal",
    "/api/retired",
    "/static/collector",
)
ORPHAN_ENDPOINT = "/internal/maintenance/sweep"


def frontend_lines(records):
    lines = []
    for record in records:
        lines.append(
            "\t".join(
                (
                    str(record["timestamp_ms"]),
                    record["req_id"],
                    record["client_ip"],
                    record["endpoint"],
                    str(record["status"]),
                    str(record["frontend_latency_ms"]),
                )
            )
        )
    return "\n".join(lines) + "\n"


def encode_pack(path, records, rng):
    if not records:
        raise ValueError("cannot encode an empty pack")
    earliest = min(record["start_ms"] for record in records)
    base = earliest - rng.randint(1, 5000)
    base_offset = base - 1_700_000_000_000
    if base_offset < 0 or base_offset > 0xFFFFFFFF:
        raise ValueError("base offset does not fit the header")

    payload = bytearray(struct.pack("<4sHHII", b"BPCK", 1, 0, len(records), base_offset))
    previous = None
    for record in records:
        endpoint = record["endpoint"].encode("utf-8")
        if not endpoint:
            raise ValueError("empty endpoint")
        start = record["start_ms"]
        delta = start - base if previous is None else start - previous
        previous = start
        payload.extend(
            struct.pack(
                "<HHHHi",
                len(endpoint),
                0,
                record["worker_id"],
                record["exit_code"],
                delta,
            )
        )
        payload.extend(endpoint)
        payload.extend(struct.pack("<q", record["duration_ms"]))
    path.write_bytes(payload)


def generate(seed, matched_count, unmatched_count, orphan_count, prefix, time_offset_ms=0):
    rng = random.Random(seed)
    endpoints = tuple(f"{prefix}{name}" for name in DEFAULT_ENDPOINTS)
    frontend = []
    backend = []
    worker_cursor = {
        worker: BASE_TIMESTAMP_MS + time_offset_ms + rng.randrange(0, 600_000)
        for worker in range(8)
    }

    for index in range(matched_count):
        endpoint = endpoints[index % len(endpoints)]
        worker = index % 8
        duration = rng.randrange(320, 981)
        start = worker_cursor[worker]
        worker_cursor[worker] = start + duration + rng.randrange(25, 110)
        before = rng.randrange(35, 375)
        after = rng.randrange(35, 345)
        frontend_start = start - before
        frontend_end = start + duration + after
        failed = rng.random() < 0.11
        exit_code = rng.choice((1, 2, 3, 17, 42)) if failed else 0
        status = rng.choice((502, 504)) if failed else rng.choice((200, 201, 202, 204))
        frontend.append(
            {
                "timestamp_ms": frontend_start,
                "req_id": f"req-{seed:08x}-{index:06d}",
                "client_ip": f"10.{(index // 251) % 251}.{index % 251}.{(index * 7) % 251 or 1}",
                "endpoint": endpoint,
                "status": status,
                "frontend_latency_ms": frontend_end - frontend_start,
            }
        )
        backend.append(
            {
                "endpoint": endpoint,
                "worker_id": worker,
                "exit_code": exit_code,
                "start_ms": start,
                "duration_ms": duration,
            }
        )

    for index in range(unmatched_count):
        frontend.append(
            {
                "timestamp_ms": BASE_TIMESTAMP_MS + time_offset_ms + rng.randrange(0, SPAN_MS),
                "req_id": f"req-{seed:08x}-u{index:06d}",
                "client_ip": f"10.201.{index % 251}.{(index * 13) % 251 or 1}",
                "endpoint": f"{prefix}{FRONTEND_ONLY_ENDPOINTS[index % len(FRONTEND_ONLY_ENDPOINTS)]}",
                "status": rng.choice((200, 404, 500)),
                "frontend_latency_ms": rng.randrange(900, 2601),
            }
        )

    for index in range(orphan_count):
        worker = index % 8
        duration = rng.randrange(250, 701)
        start = worker_cursor[worker]
        worker_cursor[worker] = start + duration + rng.randrange(25, 90)
        backend.append(
            {
                "endpoint": f"{ORPHAN_ENDPOINT}/{index:04d}",
                "worker_id": worker,
                "exit_code": rng.choice((0, 0, 1)),
                "start_ms": start,
                "duration_ms": duration,
            }
        )

    return frontend, backend


def write_dataset(frontend_dir, backend_dir, frontend, backend, seed, records_per_pack):
    frontend_path = Path(frontend_dir)
    backend_path = Path(backend_dir)
    frontend_path.mkdir(parents=True, exist_ok=True)
    backend_path.mkdir(parents=True, exist_ok=True)

    for number in range(0, len(frontend), 250):
        chunk = frontend[number : number + 250]
        path = frontend_path / f"access-{seed:08x}-{number // 250:04d}.tsv"
        path.write_text(frontend_lines(chunk), encoding="utf-8")

    shuffled = list(backend)
    random.Random(seed * 7 + 11).shuffle(shuffled)
    packs = 0
    for number in range(0, len(shuffled), records_per_pack):
        chunk = shuffled[number : number + records_per_pack]
        path = backend_path / f"worker-{seed:08x}-{packs:04d}.bpack"
        encode_pack(path, chunk, random.Random(seed * 31 + packs + 5))
        packs += 1
    return packs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--frontend-dir", default="/var/log/telemetry/frontend")
    parser.add_argument("--backend-dir", default="/var/log/telemetry/backend")
    parser.add_argument("--seed", type=int, default=902107)
    parser.add_argument("--matched", type=int, default=1200)
    parser.add_argument("--unmatched-frontend", type=int, default=180)
    parser.add_argument("--orphan-backend", type=int, default=30)
    parser.add_argument("--records-per-pack", type=int, default=150)
    parser.add_argument("--endpoint-prefix", default="")
    parser.add_argument("--time-offset-ms", type=int, default=0)
    args = parser.parse_args()
    if args.matched < 0 or args.unmatched_frontend < 0 or args.orphan_backend < 0:
        parser.error("record counts cannot be negative")
    if args.records_per_pack <= 0:
        parser.error("records-per-pack must be positive")

    frontend, backend = generate(
        args.seed,
        args.matched,
        args.unmatched_frontend,
        args.orphan_backend,
        args.endpoint_prefix,
        args.time_offset_ms,
    )
    packs = write_dataset(
        args.frontend_dir,
        args.backend_dir,
        frontend,
        backend,
        args.seed,
        args.records_per_pack,
    )
    print(
        f"generated {len(frontend)} frontend records, {len(backend)} backend records, "
        f"and {packs} packs"
    )


if __name__ == "__main__":
    main()
