#!/usr/bin/env python3
"""
TLS ClientHello Fingerprint Extractor

Connects to a replay service and produces JA3-style fingerprints from
ClientHello messages. Usage:

    python extract.py <host> <port>

One fingerprint line is printed per ClientHello, in arrival order.
Format: SSLVersion,Ciphers,Extensions,EllipticCurves,EllipticCurvePointFormats
"""
import sys
import struct
import os

sys.path.insert(0, os.path.dirname(__file__))

from utils import (
    is_grease,
    recv_exactly,
    read_uint8,
    read_uint16_be,
    read_uint24_be,
    read_opaque,
    format_fingerprint,
    parse_sni_extension,
    parse_alpn_extension,
    parse_session_ticket_extension,
    connect_to,
)
from tls_types import (
    CONTENT_HANDSHAKE,
    HS_CLIENT_HELLO,
    EXT_SUPPORTED_GROUPS,
    EXT_EC_POINT_FORMATS,
    EXT_SERVER_NAME,
    EXT_ALPN,
    EXT_SESSION_TICKET,
)


def parse_client_hello(data):
    """
    Parse a raw TLS record containing a ClientHello handshake message.

    Returns a fingerprint string, or None if the record is not a ClientHello.
    Raises ValueError on malformed input.
    """
    pos = 0

    # --- TLS Record Layer ---
    if pos + 5 > len(data):
        raise ValueError("Record too short for TLS record header")

    content_type, pos = read_uint8(data, pos)
    if content_type != CONTENT_HANDSHAKE:
        return None  # Not a handshake record

    record_version, pos = read_uint16_be(data, pos)
    record_length, pos = read_uint16_be(data, pos)
    _ = record_version  # not used in fingerprint

    if pos + record_length > len(data):
        raise ValueError(
            f"Record length {record_length} exceeds buffer size {len(data) - pos}"
        )

    # --- Handshake Layer ---
    if pos + 4 > len(data):
        raise ValueError("Buffer too short for handshake header")

    hs_type, pos = read_uint8(data, pos)
    hs_length, pos = read_uint24_be(data, pos)

    if hs_type != HS_CLIENT_HELLO:
        return None  # Not a ClientHello

    hs_end = pos + hs_length

    # --- ClientHello Body ---
    # Client version (2 bytes)
    if pos + 2 > hs_end:
        raise ValueError("ClientHello too short for version field")
    client_version, pos = read_uint16_be(data, pos)

    # Random (32 bytes)
    if pos + 32 > hs_end:
        raise ValueError("ClientHello too short for random field")
    _random, pos = read_opaque(data, pos, 32)

    # Session ID
    if pos + 1 > hs_end:
        raise ValueError("ClientHello too short for session ID length")
    sid_len, pos = read_uint8(data, pos)
    if pos + sid_len > hs_end:
        raise ValueError("ClientHello too short for session ID")
    _session_id, pos = read_opaque(data, pos, sid_len)

    # Cipher Suites
    if pos + 2 > hs_end:
        raise ValueError("ClientHello too short for cipher suites length")
    cs_total_len, pos = read_uint16_be(data, pos)
    cs_end = pos + cs_total_len
    if cs_end > hs_end:
        raise ValueError("Cipher suites length exceeds handshake body")

    ciphers = []
    while pos + 2 <= cs_end:
        cs_val, pos = read_uint16_be(data, pos)
        if not is_grease(cs_val):
            ciphers.append(cs_val)
    pos = cs_end

    # Compression Methods
    if pos + 1 > hs_end:
        raise ValueError("ClientHello too short for compression methods length")
    cm_len, pos = read_uint8(data, pos)
    if pos + cm_len > hs_end:
        raise ValueError("ClientHello too short for compression methods")
    _comp_methods, pos = read_opaque(data, pos, cm_len)

    # Extensions (optional)
    extensions = []
    curves = []
    point_formats = []
    sni_host = None
    alpn_protos = []

    if pos + 2 <= hs_end:
        ext_total_len, pos = read_uint16_be(data, pos)
        ext_block_end = pos + ext_total_len

        while pos + 4 <= ext_block_end:
            ext_type, pos = read_uint16_be(data, pos)
            ext_len, pos = read_uint16_be(data, pos)
            ext_data_start = pos
            ext_data_end = pos + ext_len

            if ext_data_end > ext_block_end:
                raise ValueError(
                    f"Extension 0x{ext_type:04x} length {ext_len} exceeds extensions block"
                )

            ext_data = data[ext_data_start:ext_data_end]

            if not is_grease(ext_type):
                extensions.append(ext_type)

                if ext_type == EXT_SUPPORTED_GROUPS:
                    # Elliptic curves / named groups list
                    # Format: uint16 list_length, then uint16 group_ids...
                    epos = 0
                    if epos + 2 <= len(ext_data):
                        groups_len = struct.unpack_from('>H', ext_data, epos)[0]
                        epos += 2
                        groups_end = epos + groups_len
                        while epos + 2 <= groups_end and epos + 2 <= len(ext_data):
                            gval = struct.unpack_from('>H', ext_data, epos)[0]
                            epos += 2
                            # Only filter GREASE from cipher suites, curves are raw
                            curves.append(gval)

                elif ext_type == EXT_EC_POINT_FORMATS:
                    # EC point formats list
                    # Format: uint8 list_length, then uint8 format_ids...
                    epos = 0
                    if epos + 1 <= len(ext_data):
                        pf_len = ext_data[epos]
                        epos += 1
                        pf_end = epos + pf_len
                        while epos < pf_end and epos < len(ext_data):
                            point_formats.append(ext_data[epos])
                            epos += 1

                elif ext_type == EXT_SERVER_NAME:
                    sni_host = parse_sni_extension(ext_data)

                elif ext_type == EXT_ALPN:
                    alpn_protos = parse_alpn_extension(ext_data)

                elif ext_type == EXT_SESSION_TICKET:
                    parse_session_ticket_extension(ext_data)

            pos = ext_data_end

    _ = sni_host   # available but not included in fingerprint fields
    _ = alpn_protos

    return format_fingerprint(client_version, ciphers, extensions, curves, point_formats)


def run(host, port):
    """Connect to host:port, read length-prefixed records, parse ClientHellos."""
    sock = connect_to(host, port)
    try:
        while True:
            # Read 4-byte little-endian length prefix
            len_data = recv_exactly(sock, 4)
            if not len_data or len(len_data) < 4:
                break
            msg_len = struct.unpack('<I', len_data)[0]
            if msg_len == 0 or msg_len > 65536:
                break

            # Read the record data
            record_data = recv_exactly(sock, msg_len)
            if not record_data:
                break

            try:
                fp = parse_client_hello(bytes(record_data))
                if fp is not None:
                    print(fp)
                    sys.stdout.flush()
            except Exception:
                pass
    except Exception:
        pass
    finally:
        sock.close()


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <host> <port>", file=sys.stderr)
        sys.exit(1)
    run(sys.argv[1], int(sys.argv[2]))
