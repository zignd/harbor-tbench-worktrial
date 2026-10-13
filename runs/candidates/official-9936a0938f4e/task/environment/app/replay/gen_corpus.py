#!/usr/bin/env python3
"""Generate corpus.bin for the TLS fingerprint replay service.

Builds a set of raw TLS ClientHello records covering various cases:
  1. Plain unfragmented ClientHello
  2. ClientHello with GREASE values 0x0a0a in ciphers and curves
  3. ClientHello with no extensions
  4. ClientHello with 0-length session ID and deflate compression
  5. ClientHello with SNI hostname of length 0
  6. ClientHello with multiple GREASE values (0x0a0a only, for corpus)
"""
import struct
import os


def build_extension(ext_type, data):
    return struct.pack('>HH', ext_type, len(data)) + data


def build_sni_ext(hostname):
    if not hostname:
        inner = struct.pack('>BH', 0, 0)
    else:
        name_bytes = hostname.encode()
        inner = struct.pack('>BH', 0, len(name_bytes)) + name_bytes
    sni_list = struct.pack('>H', len(inner)) + inner
    return build_extension(0x0000, sni_list)


def build_groups_ext(group_ids):
    body = b''.join(struct.pack('>H', g) for g in group_ids)
    return build_extension(0x000a, struct.pack('>H', len(body)) + body)


def build_point_formats_ext(formats):
    body = bytes(formats)
    return build_extension(0x000b, struct.pack('>B', len(body)) + body)


def build_sig_algs_ext(pairs):
    body = b''.join(struct.pack('>BB', h, s) for h, s in pairs)
    return build_extension(0x000d, struct.pack('>H', len(body)) + body)


def build_session_ticket_ext():
    return build_extension(0x0023, b'')


def build_extended_master_secret_ext():
    return build_extension(0x0017, b'')


def build_renegotiation_info_ext():
    return build_extension(0xff01, b'\x00')


def build_client_hello(
    version=0x0303,
    cipher_suites=None,
    compression_methods=None,
    extensions_data=None,
    session_id=None,
):
    if cipher_suites is None:
        cipher_suites = [0xC02B, 0xC02C, 0xC013, 0xC014, 0x009C, 0x009D, 0x002F]
    if compression_methods is None:
        compression_methods = [0x00]
    if session_id is None:
        session_id = b''

    random_bytes = bytes(range(32))  # deterministic

    cs_bytes = b''.join(struct.pack('>H', c) for c in cipher_suites)
    cs_field = struct.pack('>H', len(cs_bytes)) + cs_bytes

    cm_field = struct.pack('>B', len(compression_methods)) + bytes(compression_methods)

    sid_field = struct.pack('>B', len(session_id)) + session_id

    if extensions_data is not None:
        ext_field = struct.pack('>H', len(extensions_data)) + extensions_data
    else:
        ext_field = b''

    hello_body = (
        struct.pack('>H', version)
        + random_bytes
        + sid_field
        + cs_field
        + cm_field
        + ext_field
    )

    hs_header = struct.pack('>B', 0x01)  # ClientHello
    hs_len = struct.pack('>I', len(hello_body))[1:]  # 3-byte big-endian
    handshake = hs_header + hs_len + hello_body

    rec_header = struct.pack('>BHH', 0x16, 0x0301, len(handshake))
    return rec_header + handshake


def make_record(data):
    """Wrap data with a 4-byte little-endian length prefix."""
    return struct.pack('<I', len(data)) + data


def build_standard_extensions(hostname='example.com', extra_groups=None):
    groups = [0x001d, 0x0017, 0x0018]  # X25519, P-256, P-384
    if extra_groups:
        groups = extra_groups + groups
    exts = (
        build_sni_ext(hostname)
        + build_session_ticket_ext()
        + build_sig_algs_ext([(4, 1), (5, 1), (6, 1), (8, 4)])
        + build_groups_ext(groups)
        + build_point_formats_ext([0])
        + build_extended_master_secret_ext()
        + build_renegotiation_info_ext()
    )
    return exts


def main():
    records = []

    # Record 0: standard unfragmented ClientHello
    exts = build_standard_extensions('example.com')
    ch = build_client_hello(extensions_data=exts)
    records.append(ch)

    # Record 1: ClientHello with 0x0a0a GREASE in ciphers and curves (will be fragmented by server)
    grease = 0x0a0a
    ciphers_with_grease = [grease, 0xC02B, 0xC02C, 0xC013, 0x002F]
    exts = build_standard_extensions('test.example.com', extra_groups=[grease])
    ch = build_client_hello(cipher_suites=ciphers_with_grease, extensions_data=exts)
    records.append(ch)

    # Record 2: ClientHello with no extensions at all
    ch = build_client_hello(
        cipher_suites=[0xC02B, 0xC02C, 0x002F],
        extensions_data=None,
    )
    records.append(ch)

    # Record 3: ClientHello with 0-length session ID and deflate compression (will be fragmented)
    exts = build_standard_extensions('deflate.example.com')
    ch = build_client_hello(
        session_id=b'',
        compression_methods=[0x01, 0x00],
        extensions_data=exts,
    )
    records.append(ch)

    # Record 4: ClientHello with SNI length 0 (zero-length hostname)
    exts = (
        build_sni_ext('')  # empty hostname
        + build_groups_ext([0x001d, 0x0017])
        + build_point_formats_ext([0])
    )
    ch = build_client_hello(extensions_data=exts)
    records.append(ch)

    # Record 5: ClientHello with multiple 0x0a0a GREASE in cipher suites and curves (fragmented)
    all_grease = [0x0a0a] * 3
    ciphers_many_grease = all_grease + [0xC02B, 0x009C, 0x002F]
    exts = build_standard_extensions('multi.example.com', extra_groups=[0x0a0a, 0x0a0a])
    ch = build_client_hello(cipher_suites=ciphers_many_grease, extensions_data=exts)
    records.append(ch)

    # Record 6: ClientHello with only ALPN extension (no supported_groups)
    alpn_body = b'\x00\x0c\x08http/1.1'
    exts = (
        build_sni_ext('alpn.example.com')
        + build_extension(0x0010, alpn_body)
        + build_point_formats_ext([0])
    )
    ch = build_client_hello(extensions_data=exts)
    records.append(ch)

    # Record 7: Large session ID (32 bytes) (fragmented by server)
    import os as _os
    sid = bytes(range(32))
    exts = build_standard_extensions('sid.example.com')
    ch = build_client_hello(session_id=sid, extensions_data=exts)
    records.append(ch)

    # Record 8: Minimal ClientHello, TLS 1.0
    ch = build_client_hello(
        version=0x0301,
        cipher_suites=[0x002F, 0x0035],
        extensions_data=None,
    )
    records.append(ch)

    # Record 9: ClientHello with extended session ticket data
    ticket_data = bytes(range(48))
    exts = (
        build_sni_ext('ticket.example.com')
        + build_extension(0x0023, ticket_data)
        + build_groups_ext([0x001d])
        + build_point_formats_ext([0])
    )
    ch = build_client_hello(extensions_data=exts)
    records.append(ch)

    # Write corpus file
    out_path = os.path.join(os.path.dirname(__file__), 'corpus.bin')
    with open(out_path, 'wb') as f:
        for rec in records:
            f.write(make_record(rec))
    print(f"Wrote {len(records)} records to {out_path}")


if __name__ == '__main__':
    main()
