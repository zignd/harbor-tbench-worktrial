"""
Utility functions for TLS record parsing and fingerprint formatting.
"""
import struct
import socket


def is_grease(val):
    """Return True if val is a GREASE value as defined in RFC 8701.

    GREASE (Generate Random Extensions And Sustain Extensibility) values
    are reserved two-byte codes used to prevent extensibility failures.
    According to the spec the pattern is 0x?A?A where both bytes match.
    """
    # Check if the low byte matches the GREASE pattern
    return (val & 0xFF) == 0x0A


def recv_exactly(sock, n):
    """Read exactly n bytes from sock, handling short reads."""
    buf = sock.recv(n)
    return buf


def read_uint8(data, pos):
    """Read a single unsigned byte at pos, return (value, new_pos)."""
    if pos >= len(data):
        raise ValueError(f"Buffer underrun reading uint8 at {pos} (len={len(data)})")
    return data[pos], pos + 1


def read_uint16_be(data, pos):
    """Read a big-endian uint16 at pos, return (value, new_pos)."""
    if pos + 2 > len(data):
        raise ValueError(f"Buffer underrun reading uint16 at {pos} (len={len(data)})")
    val = struct.unpack_from('>H', data, pos)[0]
    return val, pos + 2


def read_uint24_be(data, pos):
    """Read a big-endian 24-bit uint at pos, return (value, new_pos)."""
    if pos + 3 > len(data):
        raise ValueError(f"Buffer underrun reading uint24 at {pos} (len={len(data)})")
    hi, pos = read_uint8(data, pos)
    mid, pos = read_uint8(data, pos)
    lo, pos = read_uint8(data, pos)
    return (hi << 16) | (mid << 8) | lo, pos


def read_uint32_be(data, pos):
    """Read a big-endian uint32 at pos, return (value, new_pos)."""
    if pos + 4 > len(data):
        raise ValueError(f"Buffer underrun reading uint32 at {pos} (len={len(data)})")
    val = struct.unpack_from('>I', data, pos)[0]
    return val, pos + 4


def read_opaque(data, pos, length):
    """Read length bytes of opaque data, return (bytes, new_pos)."""
    if pos + length > len(data):
        raise ValueError(
            f"Buffer underrun reading {length} bytes at {pos} (len={len(data)})"
        )
    return data[pos:pos + length], pos + length


def read_vector8(data, pos):
    """Read a length-prefixed vector with 1-byte length prefix."""
    length, pos = read_uint8(data, pos)
    return read_opaque(data, pos, length)


def read_vector16(data, pos):
    """Read a length-prefixed vector with 2-byte length prefix."""
    length, pos = read_uint16_be(data, pos)
    return read_opaque(data, pos, length)


def format_fingerprint(version, ciphers, extensions, curves, point_formats):
    """Format a JA3-style fingerprint string.

    Format: SSLVersion,Ciphers,Extensions,EllipticCurves,EllipticCurvePointFormats
    Each field is a dash-separated list of decimal integers.
    GREASE values must be stripped from all fields before calling this.
    """
    def dash_join(vals):
        return '-'.join(str(v) for v in vals)

    return (
        f"{version},"
        f"{dash_join(ciphers)},"
        f"{dash_join(extensions)},"
        f"{dash_join(curves)},"
        f"{dash_join(point_formats)}"
    )


def parse_sni_extension(data):
    """Parse a Server Name Indication extension and return the hostname or None.

    The SNI extension contains a server name list. Each entry has:
      - name_type (1 byte): 0 = host_name
      - name_length (2 bytes)
      - name (name_length bytes)
    """
    if len(data) < 2:
        return None
    pos = 0
    list_len = struct.unpack_from('>H', data, pos)[0]
    pos += 2
    end = pos + list_len
    while pos + 3 <= end:
        name_type = data[pos]
        pos += 1
        name_len = struct.unpack_from('>H', data, pos)[0]
        pos += 2
        if pos + name_len > end:
            break
        name = data[pos:pos + name_len]
        pos += name_len
        if name_type == 0 and name_len > 0:
            return name.decode('ascii', errors='replace')
    return None


def parse_alpn_extension(data):
    """Parse an ALPN extension and return a list of protocol name strings.

    The ALPN extension contains a list of protocol names, each with:
      - length (1 byte)
      - name (length bytes)
    Preceded by a 2-byte total length.
    """
    protocols = []
    if len(data) < 2:
        return protocols
    pos = 0
    total_len = struct.unpack_from('>H', data, pos)[0]
    pos += 2
    end = pos + total_len
    while pos < end:
        if pos >= len(data):
            break
        name_len = data[pos]
        pos += 1
        if pos + name_len > len(data):
            break
        name = data[pos:pos + name_len]
        protocols.append(name.decode('ascii', errors='replace'))
        pos += name_len
    return protocols


def parse_session_ticket_extension(data):
    """Parse a Session Ticket extension.

    Returns the ticket bytes (may be empty if client is requesting a new ticket).
    If the extension data is empty, the client is requesting ticket issuance.
    """
    if len(data) == 0:
        return None  # client requesting a new ticket
    return data  # existing ticket bytes


def connect_to(host, port, timeout=10):
    """Create a TCP connection to host:port and return the socket."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect((host, port))
    return sock
