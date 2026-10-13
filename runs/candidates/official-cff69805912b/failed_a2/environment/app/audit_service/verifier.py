"""Verifier module for the audit-log chain service."""

import hmac as _hmac
import hashlib
import configparser
import os

from . import parser as _parser
from . import chain as _chain


def _load_seed():
    cfg = configparser.ConfigParser()
    cfg.read("/app/config/chain.cfg")
    return cfg["chain"]["seed"]


def verify_log(log_path):
    """Verify the HMAC chain. Returns (True, count) or (False, first_bad_index)."""
    try:
        log_file = _parser.parse_log_file(log_path)
    except _parser.ParseError:
        return (False, 0)

    entries = _parser.get_data_entries(log_file)
    if not entries:
        return (True, 0)

    seed_hex = _load_seed()
    prev_tag_hex = seed_hex

    for i, entry in enumerate(entries):
        ok = _chain.verify_chain_entry(
            entry_index=i,
            payload=entry.payload,
            stored_tag=entry.hmac_tag,
            seed_hex=seed_hex,
            prev_tag_hex=prev_tag_hex,
            current_tag_hex=entry.hmac_tag,
        )
        if not ok:
            return (False, entry.index)
        prev_tag_hex = entry.hmac_tag

    return (True, len(entries))


def query_entry(log_path, idx):
    """Return the payload of entry at index idx, or None if not found."""
    try:
        log_file = _parser.parse_log_file(log_path)
    except _parser.ParseError:
        return None

    entry = _parser.get_entry_by_index(log_file, idx)
    if entry is None:
        return None
    return entry.payload
