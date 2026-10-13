"""
Utility functions: logging, checksum helpers, and byte-order conversions
used across the NetFlow settlement service.
"""

import logging
import struct
import socket
import hashlib
from typing import Union

_log_initialized = False


def get_logger(name: str) -> logging.Logger:
    """Return a consistently configured logger for the given name."""
    global _log_initialized
    logger = logging.getLogger(name)
    if not _log_initialized:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s %(levelname)-8s %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        )
        handler.setFormatter(formatter)
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.WARNING)
        _log_initialized = True
    return logger


def unpack_uint8(data: bytes, offset: int) -> int:
    """Unpack a single unsigned byte at *offset*."""
    return struct.unpack_from('!B', data, offset)[0]


def unpack_uint16(data: bytes, offset: int) -> int:
    """Unpack a big-endian unsigned 16-bit integer at *offset*."""
    return struct.unpack_from('!H', data, offset)[0]


def unpack_uint32(data: bytes, offset: int) -> int:
    """Unpack a big-endian unsigned 32-bit integer at *offset*."""
    return struct.unpack_from('!I', data, offset)[0]


def unpack_ipv4(data: bytes, offset: int) -> str:
    """Unpack a 4-byte IPv4 address at *offset* and return dotted-decimal."""
    raw = struct.unpack_from('!4B', data, offset)
    return '.'.join(str(b) for b in raw)


def pack_uint8(value: int) -> bytes:
    return struct.pack('!B', value & 0xFF)


def pack_uint16(value: int) -> bytes:
    return struct.pack('!H', value & 0xFFFF)


def pack_uint32(value: int) -> bytes:
    return struct.pack('!I', value & 0xFFFFFFFF)


def pack_ipv4(addr: str) -> bytes:
    """Pack a dotted-decimal IPv4 address string into 4 bytes."""
    return socket.inet_aton(addr)


def ip_to_int(addr: str) -> int:
    """Convert a dotted-decimal IPv4 address to an integer."""
    parts = addr.split('.')
    result = 0
    for p in parts:
        result = (result << 8) | int(p)
    return result


def int_to_ip(value: int) -> str:
    """Convert a 32-bit integer to a dotted-decimal IPv4 address string."""
    return '.'.join(str((value >> (8 * i)) & 0xFF) for i in (3, 2, 1, 0))


def internet_checksum(data: bytes) -> int:
    """
    Compute the Internet checksum (RFC 1071) over *data*.
    Returns the one's complement of the one's complement sum.
    """
    if len(data) % 2 != 0:
        data += b'\x00'
    total = 0
    for i in range(0, len(data), 2):
        word = (data[i] << 8) + data[i + 1]
        total += word
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    return ~total & 0xFFFF


def validate_checksum(data: bytes, expected: int) -> bool:
    """Return True if the Internet checksum of *data* matches *expected*."""
    return internet_checksum(data) == expected


def file_digest(path: str, algorithm: str = 'sha256') -> str:
    """Compute the hex digest of a file using the given hash algorithm."""
    h = hashlib.new(algorithm)
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def pretty_bytes(n: int) -> str:
    """Format a byte count as a human-readable string."""
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if abs(n) < 1024:
            return f'{n:.1f} {unit}'
        n /= 1024
    return f'{n:.1f} PB'


class RingBuffer:
    """Fixed-size circular buffer used for sliding-window diagnostics."""

    def __init__(self, capacity: int):
        self._buf = [None] * capacity
        self._capacity = capacity
        self._head = 0
        self._size = 0

    def push(self, item) -> None:
        self._buf[self._head % self._capacity] = item
        self._head += 1
        if self._size < self._capacity:
            self._size += 1

    def items(self) -> list:
        if self._size < self._capacity:
            return list(self._buf[: self._size])
        start = self._head % self._capacity
        return self._buf[start:] + self._buf[:start]

    def __len__(self) -> int:
        return self._size
