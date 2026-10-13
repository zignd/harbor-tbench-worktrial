#!/usr/bin/env python3
"""Create deterministic binary Monte Carlo checkpoint spools."""

import argparse
import hashlib
import math
import random
import struct
from pathlib import Path

HEADER_BYTES = 128
RECORD_BYTES = 64
MAGIC = b"QDR1\x00\x00\x00\x00"


def make_header(batch_id: str, worker_id: str, records: int) -> bytes:
    lines = [
        "QUANT-SPOOL-V1",
        f"batch_id:{batch_id}",
        f"worker_id:{worker_id}",
        f"records:{records}",
        "payload:qtr-double-v1",
        "---END-HEADER---",
    ]
    text = "\n".join(lines) + "\n"
    if len(text) > HEADER_BYTES:
        raise ValueError("spool header is too long")
    return text.encode("ascii").ljust(HEADER_BYTES, b"#")


def trade_id(index: int) -> str:
    return f"TR-{index:05d}"


def packed_record(index: int, drift: float, variance: float, noise: bytes) -> bytes:
    identifier = trade_id(index).encode("ascii")
    if len(identifier) > 16:
        raise ValueError("trade identifier is too long")
    record = bytearray(RECORD_BYTES)
    record[0:8] = MAGIC
    record[8:24] = identifier.ljust(16, b"\0")
    record[24:32] = struct.pack("<Q", index)
    record[32:40] = struct.pack("<d", drift)
    record[40:48] = struct.pack("<d", variance)
    record[48:64] = noise[:16].ljust(16, b"\0")
    return bytes(record)


def create_spool(path: Path, batch_id: str, worker_id: str, values):
    random_source = random.Random(f"noise:{batch_id}")
    payload = bytearray()
    for index, (drift, variance) in enumerate(values):
        noise = bytes(random_source.randrange(256) for _ in range(16))
        payload.extend(packed_record(index, drift, variance, noise))
    blob = make_header(batch_id, worker_id, len(values)) + payload
    path.write_bytes(blob)
    return hashlib.sha256(blob).hexdigest()


def curve_values(count: int, seed: str):
    source = random.Random(seed)
    return [
        (source.uniform(-0.030, 0.033), source.uniform(0.010, 0.075))
        for _ in range(count)
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    for stale_file in output.glob("*.spool"):
        stale_file.unlink()

    layout = [
        ("MC-STG-A", "sim-node-01", 14, "stage-alpha"),
        ("MC-STG-B", "sim-node-02", 18, "stage-bravo"),
        ("MC-STG-C", "sim-node-03", 16, "stage-charlie"),
        ("MC-STG-D", "sim-node-01", 15, "stage-delta"),
        ("MC-STG-E", "sim-node-02", 17, "stage-echo"),
        ("MC-STG-F", "sim-node-03", 13, "stage-foxtrot"),
    ]
    overrides = {
        "MC-STG-C": {3: (0.041, 0.072)},
        "MC-STG-E": {6: (0.029, 0.081), 12: (0.036, 0.069)},
    }
    for batch_id, worker_id, count, curve in layout:
        values = curve_values(count, f"{args.seed}:{curve}")
        for index, replacement in overrides.get(batch_id, {}).items():
            if index < len(values):
                values[index] = replacement
        create_spool(output / f"{batch_id}.spool", batch_id, worker_id, values)


if __name__ == "__main__":
    main()
