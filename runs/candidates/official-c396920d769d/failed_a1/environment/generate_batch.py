#!/usr/bin/env python3
"""Deterministic binary batch generator for the sensor pipeline.

Usage:
    python3 generate_batch.py <output.bin> <num_records> [batch_id] [seed]

Defaults:
    batch_id = 1
    seed     = 42

Output format (see /app/docs/format.md):
    8-byte header: batch_id (i32 LE) + sample_count (i32 LE)
    4 bytes per sample: i32 LE
"""
import struct
import random
import sys
import os


def generate_batch(num_records: int, batch_id: int = 1, seed: int = 42) -> bytes:
    """Generate a binary batch with `num_records` samples."""
    rng = random.Random(seed ^ (batch_id * 0x9E3779B9))
    header = struct.pack('<ii', batch_id, num_records)
    samples = bytearray()
    for _ in range(num_records):
        # Sensor values are signed 32-bit integers in range [-32768, 32767]
        # (simulating 16-bit ADC readings stored as i32)
        val = rng.randint(-32768, 32767)
        samples += struct.pack('<i', val)
    return header + bytes(samples)


def main():
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    output_path = sys.argv[1]
    num_records = int(sys.argv[2])
    batch_id = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else 42

    data = generate_batch(num_records, batch_id, seed)

    with open(output_path, 'wb') as f:
        f.write(data)

    print(f"Generated {num_records} records for batch_id={batch_id} "
          f"(seed={seed}) -> {output_path} ({len(data)} bytes)",
          file=sys.stderr)


if __name__ == '__main__':
    main()
