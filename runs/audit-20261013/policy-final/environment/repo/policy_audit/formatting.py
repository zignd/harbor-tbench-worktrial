"""Stable output formatting used by batch and command-line clients."""
import json

FIELDS = ("request_sequence", "tenant", "decision", "matched_policy_revision", "reason")

def canonical_record(row):
    return {field: row[field] for field in FIELDS}

def encode(row):
    return json.dumps(canonical_record(row), separators=(",", ":"), ensure_ascii=False)

def encode_many(rows):
    return "\n".join(encode(row) for row in rows)

def parse_line(line):
    value = json.loads(line)
    if tuple(value) != FIELDS:
        raise ValueError("unexpected audit record fields")
    return value
