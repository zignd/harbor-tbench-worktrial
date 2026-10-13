"""Utility functions for the log pipeline."""

import json
import os
import re
from pathlib import Path


def load_state(state_path: str) -> dict:
    """Load the state file mapping service->set of processed sequence numbers."""
    if not os.path.exists(state_path):
        return {}
    with open(state_path, 'r') as f:
        raw = json.load(f)
    return {svc: set(seqs) for svc, seqs in raw.items()}


def save_state(state: dict, state_path: str) -> None:
    """Save the state file, converting sets to sorted lists for JSON."""
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    serializable = {svc: sorted(seqs) for svc, seqs in state.items()}
    with open(state_path, 'w') as f:
        json.dump(serializable, f, indent=2)


def parse_log_line(line: str) -> dict | None:
    """Parse a single log line into its components.

    Returns a dict with keys: timestamp, sequence, service, message
    or None if the line does not match the expected format.
    """
    pattern = r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}) Z \[(\d+)\] (.+)$'
    match = re.match(pattern, line.strip())
    if not match:
        return None
    return {
        'timestamp': match.group(1),
        'sequence': int(match.group(2)),
        'message': match.group(3),
    }


def extract_timestamp(line: str) -> str | None:
    """Extract the timestamp from a log line."""
    parsed = parse_log_line(line)
    if parsed is None:
        return None
    return parsed['timestamp']


def extract_sequence(line: str) -> int | None:
    """Extract the sequence number from a log line."""
    parsed = parse_log_line(line)
    if parsed is None:
        return None
    return parsed['sequence']
