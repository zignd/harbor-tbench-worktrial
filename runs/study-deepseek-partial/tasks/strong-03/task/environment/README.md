# Allocator Binary Usage

The legacy `allocator` binary is located at `/usr/local/bin/allocator`.

## Synopsis

```
allocator <input.csv>
```

## Input Format

A CSV file with a header row and three columns:
- `query_id` (integer)
- `load` (integer, non-negative)
- `timestamp` (integer, Unix epoch seconds)

## Output

A CSV written to stdout with header `query_id,assigned_shard`. Each row maps
an input query to one of three shards (0, 1, or 2).

## Notes

- The source code is not available; this is a compiled binary only.
- The binary is part of the legacy shard allocation infrastructure and is
  scheduled for retirement.
- A pure-SQL replacement should produce identical output for any valid input.
- The binary expects the CSV to be well-formed; malformed lines are silently
  skipped after the header.
