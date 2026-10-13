# Sensor Pipeline Binary Format

## Overview

The pipeline reads and writes sensor data in a compact binary format.
All multi-byte integers are little-endian.

## Input File Format (`input.bin`)

The input file contains one or more batches concatenated with no separator.

### Batch Structure

Each batch begins with an 8-byte header:

| Offset | Size | Type | Description |
|--------|------|------|-------------|
| 0      | 4    | i32  | `batch_id`: unique identifier for this batch |
| 4      | 4    | i32  | `sample_count`: number of samples that follow |

Immediately following the header are `sample_count` samples, each 4 bytes:

| Offset | Size | Type | Description |
|--------|------|------|-------------|
| 0      | 4    | i32  | raw sensor reading (signed, little-endian) |

Total batch size: `8 + 4 * sample_count` bytes.

### Example

A batch with `batch_id=1` and 3 samples `[100, 200, 300]`:

```
01 00 00 00   # batch_id = 1
03 00 00 00   # sample_count = 3
64 00 00 00   # sample[0] = 100
C8 00 00 00   # sample[1] = 200
2C 01 00 00   # sample[2] = 300
```

## Output Database Schema (`results.db`)

SQLite database with a single table:

```sql
CREATE TABLE results (
    batch_id       INTEGER,
    sample_count   INTEGER,
    fixed_mean     INTEGER,
    fixed_variance INTEGER,
    checksum       INTEGER
);
```

### Column Descriptions

- **batch_id**: The batch identifier from the input header.
- **sample_count**: Number of samples in the batch.
- **fixed_mean**: Population mean in Q16.16 fixed-point format.
- **fixed_variance**: Population variance in Q16.16 fixed-point format.
- **checksum**: CRC32 integrity check of the raw sample data.

## Q16.16 Fixed-Point Format

Fixed-point values use 16 integer bits and 16 fractional bits:

- Scale factor: 65536 (= 2^16)
- To convert to float: `value / 65536.0`
- To convert from float (truncated): `int(value * 65536.0)`
- Range: approximately -32768.0 to +32767.9999847

Examples:

| Float value | Q16.16 integer |
|-------------|----------------|
| 0.0         | 0              |
| 1.0         | 65536          |
| 1.5         | 98304          |
| -1.0        | -65536         |
| 0.5         | 32768          |

## Checksum Algorithm

The `checksum` column stores the CRC32 of the raw sample bytes.

Computation:
1. For each sample in order, take its 4-byte little-endian representation.
2. Feed the bytes to a CRC32 hasher using the standard IEEE 802.3 polynomial
   (0xEDB88320, reflected).
3. The final 32-bit CRC value is stored as a signed 64-bit integer in SQLite.

This is the same algorithm used by `crc32fast` (Rust) and Python's `binascii.crc32`.

## Batch Generator

The file `/app/data/generate_batch.py` generates deterministic test batches:

```
python3 /app/data/generate_batch.py <output.bin> <num_records> [batch_id] [seed]
```

Defaults: `batch_id=1`, `seed=42`. The generator produces reproducible output
given the same arguments, allowing both the reference binary and the pipeline
under test to be run on identical inputs.

## Running the Pipeline

Build and run with the convenience script:

```
bash /app/run_pipeline.sh
```

Or manually:

```
cd /app/src && cargo build --release 2>/dev/null
/app/src/target/release/sensor_pipeline /app/data/input.bin /app/db/results.db
```

Run the reference binary:

```
/app/bin/accumulator_ref /app/data/input.bin /app/db/ref_results.db
```
