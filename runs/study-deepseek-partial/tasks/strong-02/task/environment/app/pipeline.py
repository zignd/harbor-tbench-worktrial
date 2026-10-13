#!/usr/bin/env python3
"""Log Pipeline - decrypts, merges, deduplicates, and outputs combined logs."""

import json
import os
import subprocess
import sys

import yaml

from utils import load_state, parse_log_line, save_state


def load_config(config_path: str) -> dict:
    """Load the YAML configuration file."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config


def decrypt_file(enc_path: str, service_name: str, master_key: str) -> str:
    """Decrypt a single .enc file using the external decrypt_tool binary.

    The decrypt_tool expects two command-line arguments:
    1. The derived key as a hex string (32 bytes = 64 hex chars)
    2. The path to the encrypted file

    It writes the decrypted plaintext to stdout.
    """
    # Derive the per-service key using HKDF
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives import hashes

    derived_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=service_name.encode('utf-8'),
    ).derive(master_key.encode('utf-8'))

    key_hex = derived_key.hex()

    # Call the external decrypt tool
    result = subprocess.run(
        ['/app/bin/decrypt_tool', key_hex, enc_path],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        print(f"Error decrypting {enc_path}: {result.stderr}", file=sys.stderr)
        return ""
    return result.stdout


def process_logs(config_path: str, output_path: str, state_path: str) -> None:
    """Main pipeline processing function."""
    config = load_config(config_path)
    master_key = config['master_key']
    services = config['services']

    state = load_state(state_path)

    all_records = []

    for service in services:
        log_dir = os.path.join('/app/logs', service)
        if not os.path.isdir(log_dir):
            print(f"Warning: log directory {log_dir} not found, skipping.", file=sys.stderr)
            continue

        if service not in state:
            state[service] = set()

        enc_files = sorted([
            f for f in os.listdir(log_dir)
            if f.endswith('.enc')
        ])

        for enc_file in enc_files:
            enc_path = os.path.join(log_dir, enc_file)
            decrypted_text = decrypt_file(enc_path, service, master_key)

            for line in decrypted_text.splitlines():
                line = line.strip()
                if not line:
                    continue
                parsed = parse_log_line(line)
                if parsed is None:
                    continue

                seq = parsed['sequence']
                if seq in state[service]:
                    continue

                state[service].add(seq)
                all_records.append({
                    'service': service,
                    'timestamp': parsed['timestamp'],
                    'sequence': seq,
                    'message': parsed['message'],
                })

    # Sort all records by timestamp, then by service name for determinism
    all_records.sort(key=lambda r: (r['timestamp'], r['service'], r['sequence']))

    # Write output
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        for rec in all_records:
            line = f"{rec['timestamp']} Z [{rec['sequence']}] [{rec['service']}] {rec['message']}\n"
            f.write(line)

    # Save state
    save_state(state, state_path)

    print(f"Pipeline complete: {len(all_records)} records written to {output_path}")


if __name__ == '__main__':
    process_logs(
        config_path='/app/config.yaml',
        output_path='/app/output/combined.log',
        state_path='/app/state/processed.json',
    )
