#!/usr/bin/env python3
"""Deterministic log generator for the audit-log HMAC chain service.

Usage: python3 generate_logs.py [output_dir]
Generates log files in output_dir (default: /app/logs/).

Log format
----------
Header: AUDIT_LOG v1 node=<name> created=<ISO8601>
Entries: <index>|<payload>|<hmac_sha256_hex>

HMAC chain
----------
Entry 0: key = bytes.fromhex(seed_hex); tag = HMAC-SHA256(key, payload.encode())
Entry N>0: key = HMAC-SHA256(prev_tag.encode('ascii'), b'key'); tag = HMAC-SHA256(key, payload.encode())

See /app/tools/chain_spec.md for the authoritative specification.
"""

import hmac as _hmac
import hashlib
import configparser
import os
import sys
import random
import datetime


def load_seed(cfg_path="/app/config/chain.cfg"):
    cfg = configparser.ConfigParser()
    cfg.read(cfg_path)
    return cfg["chain"]["seed"]


def derive_key(i, seed_hex, prev_tag_hex):
    """Derive the HMAC key for entry i."""
    if i == 0:
        return bytes.fromhex(seed_hex)
    return _hmac.new(
        prev_tag_hex.encode("ascii"),
        b"key",
        hashlib.sha256,
    ).digest()


def compute_tag(key, payload):
    """Compute HMAC-SHA256 tag for payload."""
    return _hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def make_payload(action, user_id, seq, ts, ref):
    return f"action={action} user={user_id} seq={seq} ts={ts} data=ref-{ref}"


def write_log(path, payloads, seed_hex, node="node-01",
             tamper_payload_idx=None, tamper_tag_idx=None):
    """Write a log file with correct HMAC chain, optionally with tampering."""
    created = "2025-06-15T10:00:00Z"
    lines = [f"AUDIT_LOG v1 node={node} created={created}\n"]
    prev_tag_hex = seed_hex
    for i, payload in enumerate(payloads):
        key = derive_key(i, seed_hex, prev_tag_hex)
        tag = compute_tag(key, payload)
        write_payload = payload
        write_tag = tag
        if tamper_payload_idx == i:
            write_payload = payload + "_TAMPERED"
        if tamper_tag_idx == i:
            write_tag = "0" * 64
        lines.append(f"{i}|{write_payload}|{write_tag}\n")
        prev_tag_hex = tag
    with open(path, "w") as f:
        f.writelines(lines)


ACTIONS = ["login", "logout", "read", "write", "delete",
           "verify", "approve", "reject", "execute",
           "notify", "transaction", "audit"]


def gen_payloads(n, seed=42):
    """Generate n deterministic realistic payloads."""
    rng = random.Random(seed)
    base = datetime.datetime(2025, 1, 1)
    payloads = []
    for i in range(n):
        action = rng.choice(ACTIONS)
        user_id = rng.randint(1000, 9999)
        days = rng.randint(0, 364)
        hours = rng.randint(0, 23)
        mins = rng.randint(0, 59)
        secs = rng.randint(0, 59)
        ts = (base + datetime.timedelta(days=days, hours=hours,
              minutes=mins, seconds=secs)).strftime("%Y-%m-%dT%H:%M:%SZ")
        ref = rng.randint(10000, 99999)
        payloads.append(make_payload(action, user_id, i, ts, ref))
    return payloads


def main():
    seed_hex = load_seed()
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "/app/logs"
    os.makedirs(out_dir, exist_ok=True)

    p10 = gen_payloads(10, seed=1)
    write_log(f"{out_dir}/valid_10.log", p10, seed_hex, node="node-01")

    p20 = gen_payloads(20, seed=2)
    write_log(f"{out_dir}/valid_20.log", p20, seed_hex, node="node-02")

    write_log(f"{out_dir}/tampered_payload_2.log", p10, seed_hex,
              node="node-03", tamper_payload_idx=2)
    write_log(f"{out_dir}/tampered_payload_5.log", p10, seed_hex,
              node="node-04", tamper_payload_idx=5)

    write_log(f"{out_dir}/tampered_tag_3.log", p10, seed_hex,
              node="node-05", tamper_tag_idx=3)
    write_log(f"{out_dir}/tampered_tag_7.log", p10, seed_hex,
              node="node-06", tamper_tag_idx=7)

    p_nl = gen_payloads(20, seed=3)
    p_nl[3] = r"event_3_line1\nevent_3_line2\nevent_3_line3"
    p_nl[17] = r"event_17_multi\nline\npayload"
    write_log(f"{out_dir}/newlines_20.log", p_nl, seed_hex, node="node-07")

    p500 = gen_payloads(500, seed=4)
    write_log(f"{out_dir}/large_500.log", p500, seed_hex, node="node-08")

    print(f"Generated 8 log files in {out_dir}/")


if __name__ == "__main__":
    main()
