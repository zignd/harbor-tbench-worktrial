"""
utils.py - Logging helpers and miscellaneous utilities for the NetFlow
settlement service.
"""

import logging
import os
import socket
import struct
from typing import Optional


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a module-level logger with a consistent format.

    Loggers are cached by the standard logging machinery, so calling this
    multiple times with the same name returns the same instance.
    """
    logger = logging.getLogger(f'netflow.{name}')
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                '%(asctime)s %(levelname)-8s %(name)s: %(message)s',
                datefmt='%Y-%m-%dT%H:%M:%S',
            )
        )
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


# ---------------------------------------------------------------------------
# IP address helpers
# ---------------------------------------------------------------------------

def ip_to_int(ip_str: str) -> int:
    """Convert a dotted-decimal IPv4 string to a 32-bit integer."""
    try:
        packed = socket.inet_aton(ip_str)
        return struct.unpack('!I', packed)[0]
    except (socket.error, struct.error) as exc:
        raise ValueError(f'Invalid IPv4 address: {ip_str!r}') from exc


def int_to_ip(value: int) -> str:
    """Convert a 32-bit integer to a dotted-decimal IPv4 string."""
    try:
        return socket.inet_ntoa(struct.pack('!I', value & 0xFFFFFFFF))
    except (socket.error, struct.error) as exc:
        raise ValueError(f'Cannot convert {value!r} to IP') from exc


def parse_cidr(cidr: str):
    """Parse a CIDR notation string into (network_int, prefix_len).

    Example::

        parse_cidr('10.0.0.0/8')  # -> (167772160, 8)

    Raises ValueError on malformed input.
    """
    if '/' not in cidr:
        raise ValueError(f'Not a CIDR notation: {cidr!r}')
    prefix, length_str = cidr.rsplit('/', 1)
    try:
        prefix_len = int(length_str)
    except ValueError as exc:
        raise ValueError(f'Invalid prefix length in {cidr!r}') from exc
    if not 0 <= prefix_len <= 32:
        raise ValueError(f'Prefix length out of range in {cidr!r}')
    network_int = ip_to_int(prefix)
    # Mask off host bits so callers can rely on the network address
    if prefix_len < 32:
        mask = (0xFFFFFFFF << (32 - prefix_len)) & 0xFFFFFFFF
        network_int = network_int & mask
    return network_int, prefix_len


# ---------------------------------------------------------------------------
# Struct helpers
# ---------------------------------------------------------------------------

def read_uint8(data: bytes, offset: int) -> int:
    """Read one unsigned byte at *offset*."""
    return data[offset]


def read_uint16_be(data: bytes, offset: int) -> int:
    """Read a big-endian unsigned 16-bit integer at *offset*."""
    return struct.unpack_from('!H', data, offset)[0]


def read_uint32_be(data: bytes, offset: int) -> int:
    """Read a big-endian unsigned 32-bit integer at *offset*."""
    return struct.unpack_from('!I', data, offset)[0]


def bytes_to_uint(data: bytes, big_endian: bool = True) -> int:
    """Interpret an arbitrary-length byte string as an unsigned integer."""
    if not data:
        return 0
    order = 'big' if big_endian else 'little'
    return int.from_bytes(data, byteorder=order)


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def read_binary_file(path: str) -> bytes:
    """Read an entire binary file and return its contents.

    Raises FileNotFoundError if the file does not exist, OSError on other
    I/O errors.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f'No such file: {path!r}')
    with open(path, 'rb') as fh:
        return fh.read()


def safe_filename(name: str) -> str:
    """Strip directory components and return only the base filename."""
    return os.path.basename(name)


# ---------------------------------------------------------------------------
# Checksum / integrity
# ---------------------------------------------------------------------------

def simple_checksum(data: bytes) -> int:
    """Compute a simple additive checksum over *data* (32-bit wrap).

    This is not a cryptographic hash; it is used only for quick sanity
    checks on decoded record counts.
    """
    total = 0
    for byte in data:
        total = (total + byte) & 0xFFFFFFFF
    return total


def verify_record_count(records, declared_count: int, source: str = '') -> bool:
    """Log a warning if the number of decoded records differs from *declared_count*.

    Returns True when counts match, False otherwise.
    """
    logger = get_logger('utils')
    actual = len(records)
    if actual != declared_count:
        logger.warning(
            '%sDeclared %d records but decoded %d',
            f'{source}: ' if source else '',
            declared_count,
            actual,
        )
        return False
    return True
