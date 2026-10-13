"""
CIDR-prefix trie for mapping source IPv4 addresses to ASN counterparty IDs.
Loads from a CSV with columns: prefix, asn
Example: 10.0.0.0/8, AS64501
"""

import csv
import struct
import socket
from typing import Optional, List, Tuple
from .utils import get_logger

log = get_logger(__name__)


def _parse_cidr(cidr: str) -> Tuple[int, int]:
    """
    Parse a CIDR notation string into (network_int, mask_int).
    Returns (network, mask) both as 32-bit unsigned integers.
    """
    cidr = cidr.strip()
    if '/' in cidr:
        addr_str, prefix_len_str = cidr.split('/', 1)
        prefix_len = int(prefix_len_str)
    else:
        addr_str = cidr
        prefix_len = 32
    packed = socket.inet_aton(addr_str.strip())
    addr_int = struct.unpack('!I', packed)[0]
    if prefix_len == 0:
        mask = 0
    else:
        mask = ((1 << 32) - 1) ^ ((1 << (32 - prefix_len)) - 1)
    network = addr_int & mask
    return network, mask


def _ip_to_int(addr: str) -> int:
    packed = socket.inet_aton(addr.strip())
    return struct.unpack('!I', packed)[0]


class _TrieNode:
    """Binary trie node for longest-prefix matching."""
    __slots__ = ('children', 'asn', 'prefix_len')

    def __init__(self):
        self.children = [None, None]
        self.asn: Optional[str] = None
        self.prefix_len: int = -1


class ASNLookup:
    """
    Longest-prefix-match lookup table mapping IPv4 CIDR blocks to ASN IDs.

    Usage:
        trie = ASNLookup('/app/data/asn_map.csv')
        asn = trie.lookup('203.0.113.5')  # returns e.g. 'AS64502' or None
    """

    def __init__(self, csv_path: str):
        self._root = _TrieNode()
        self._entries: List[Tuple[str, int, str]] = []  # (prefix_str, prefix_len, asn)
        self._load(csv_path)

    def _load(self, csv_path: str) -> None:
        loaded = 0
        with open(csv_path, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                prefix = row['prefix'].strip()
                asn = row['asn'].strip()
                try:
                    network, mask = _parse_cidr(prefix)
                    prefix_len = bin(mask).count('1')
                    self._insert(network, prefix_len, asn)
                    self._entries.append((prefix, prefix_len, asn))
                    loaded += 1
                except Exception as exc:
                    log.warning('Skipping bad prefix %r: %s', prefix, exc)
        log.info('ASNLookup: loaded %d prefixes from %s', loaded, csv_path)

    def _insert(self, network: int, prefix_len: int, asn: str) -> None:
        node = self._root
        for bit_pos in range(31, 31 - prefix_len, -1):
            bit = (network >> bit_pos) & 1
            if node.children[bit] is None:
                node.children[bit] = _TrieNode()
            node = node.children[bit]
        # Always overwrite so the last-loaded entry for a prefix wins.
        node.asn = asn
        node.prefix_len = prefix_len

    def lookup(self, addr: str) -> Optional[str]:
        """
        Return the ASN for the longest matching prefix, or None if no match.
        """
        try:
            addr_int = _ip_to_int(addr)
        except Exception:
            log.debug('ASNLookup.lookup: invalid address %r', addr)
            return None

        node = self._root
        best_asn: Optional[str] = None

        for bit_pos in range(31, -1, -1):
            if node.asn is not None:
                best_asn = node.asn
            bit = (addr_int >> bit_pos) & 1
            child = node.children[bit]
            if child is None:
                break
            node = child

        # Check the last node reached
        if node.asn is not None:
            best_asn = node.asn

        return best_asn

    def all_asns(self) -> List[str]:
        """Return a sorted list of all distinct ASN IDs in the table."""
        seen = set()
        for _, _, asn in self._entries:
            seen.add(asn)
        return sorted(seen)

    def entry_count(self) -> int:
        """Return the number of CIDR entries loaded."""
        return len(self._entries)

    def __repr__(self) -> str:
        return f'ASNLookup({len(self._entries)} prefixes)'


class CachingASNLookup(ASNLookup):
    """
    ASNLookup with a simple LRU-ish cache for hot paths where the same
    source IP appears in many consecutive flow records.
    """

    def __init__(self, csv_path: str, cache_size: int = 4096):
        super().__init__(csv_path)
        self._cache: dict = {}
        self._cache_size = cache_size

    def lookup(self, addr: str) -> Optional[str]:
        result = self._cache.get(addr)
        if result is not None:
            return result
        result = super().lookup(addr)
        if len(self._cache) >= self._cache_size:
            # Evict an arbitrary entry to bound memory
            self._cache.pop(next(iter(self._cache)))
        self._cache[addr] = result
        return result
