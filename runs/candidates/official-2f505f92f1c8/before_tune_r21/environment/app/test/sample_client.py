#!/usr/bin/env python3
"""
sample_client.py - send two short WAL records to the audit service and
print the returned tags.  This script exercises only the short-record
path; it does not test large records or refund lookups against real
database rows.
"""
import socket
import struct
import sys

HOST = '127.0.0.1'
PORT = 7741


def build_record(record_type, txid, charge_txid=0, payload=b''):
    """Build a binary WAL record (big-endian header + payload)."""
    hdr = struct.pack('>BQQh', record_type, txid, charge_txid,
                     len(payload))
    # struct '>BQQh' = 1+8+8+2 = 19 bytes
    # But '>h' is signed; use '>H' for unsigned payload_len
    hdr = struct.pack('>BQQH', record_type, txid, charge_txid, len(payload))
    return hdr + payload


def send_record(sock, record_bytes):
    """Hex-encode and send a record; return the response tag."""
    line = record_bytes.hex() + '\n'
    sock.sendall(line.encode())
    resp = b''
    while b'\n' not in resp:
        chunk = sock.recv(4096)
        if not chunk:
            break
        resp += chunk
    return resp.decode().strip()


def main():
    # Record 1: a short charge record (16 bytes binary)
    rec1 = build_record(0x01, txid=1001, payload=b'\x00' * 0)
    # Record 2: a short refund record with charge_txid=0 (resolver needed)
    # txid=0 so the sample resolver always returns nothing - safe demo
    rec2 = build_record(0x02, txid=0, charge_txid=0, payload=b'audit')

    with socket.create_connection((HOST, PORT), timeout=5) as s:
        tag1 = send_record(s, rec1)
        tag2 = send_record(s, rec2)

    print(f'charge  tag: {tag1}')
    print(f'refund  tag: {tag2}')


if __name__ == '__main__':
    main()
