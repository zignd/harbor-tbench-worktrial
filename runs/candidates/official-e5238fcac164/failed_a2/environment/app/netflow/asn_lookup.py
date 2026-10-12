"""
asn_lookup.py - CIDR-prefix longest-match trie for IP-to-ASN resolution.

The trie is built once from a CSV file containing (cidr, asn) rows and then
queried for each flow record's source IP address.  Longest-prefix match
semantics are implemented so that a /24 entry shadows a less-specific /16
for addresses that fall in both ranges.

CSV format expected::

    cidr,asn
    10.0.0.0/8,AS64512
    192.168.1.0/24,AS64514
    ...

Addresses that do not match any prefix are returned as None; callers
typically attribute those bytes to an "unknown" bucket and exclude them
from settlement totals.
"""

import csv
import socket
import struct
from typing import Dict, List, Optional, Tuple

from netflow.utils import get_logger, ip_to_int, parse_cidr

logger = get_logger('asn_lookup')


# ---------------------------------------------------------------------------
# Trie node
# ---------------------------------------------------------------------------

class _TrieNode:
    """A single node in the binary trie."""

    __slots__ = ('children', 'asn')

    def __init__(self):
        self.children: List[Optional['_TrieNode']] = [None, None]
        self.asn: Optional[str] = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class AsnLookup:
    """Longest-prefix-match trie keyed by IPv4 CIDR prefixes.

    Usage::

        lut = AsnLookup()
        lut.load_csv('/app/data/asn_map.csv')
        asn = lut.lookup('10.1.5.5')   # -> 'AS64512'

    """

    def __init__(self):
        self._root = _TrieNode()
        self._prefix_count = 0

    # ------------------------------------------------------------------
    # Building the trie
    # ------------------------------------------------------------------

    def insert(self, cidr: str, asn: str) -> None:
        """Insert one CIDR prefix -> ASN mapping into the trie."""
        network_int, prefix_len = parse_cidr(cidr)
        node = self._root
        for bit_pos in range(31, 31 - prefix_len, -1):
            bit = (network_int >> bit_pos) & 1
            if node.children[bit] is None:
                node.children[bit] = _TrieNode()
            node = node.children[bit]
        # Always overwrite so that the last-loaded entry wins when two
        # entries have identical prefix lengths for the same network.
        node.asn = asn
        self._prefix_count += 1

    def load_csv(self, path: str) -> int:
        """Load CIDR-to-ASN mappings from a CSV file.

        The CSV must have columns ``cidr`` and ``asn`` (case-insensitive
        header).  Returns the number of prefixes loaded.

        Raises FileNotFoundError if the file cannot be opened.
        """
        loaded = 0
        with open(path, newline='') as fh:
            reader = csv.DictReader(fh)
            for lineno, row in enumerate(reader, start=2):
                try:
                    cidr = row['cidr'].strip()
                    asn = row['asn'].strip()
                    if not cidr or not asn:
                        logger.warning('Line %d: empty cidr or asn, skipping', lineno)
                        continue
                    self.insert(cidr, asn)
                    loaded += 1
                except (KeyError, ValueError) as exc:
                    logger.warning('Line %d: skipping bad entry: %s', lineno, exc)
        logger.info('Loaded %d CIDR prefixes from %s', loaded, path)
        return loaded

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def lookup(self, ip_str: str) -> Optional[str]:
        """Return the ASN for *ip_str* using longest-prefix match.

        Returns None if no prefix matches.
        """
        try:
            ip_int = ip_to_int(ip_str)
        except ValueError:
            logger.debug('Cannot parse IP %r, returning None', ip_str)
            return None
        return self._lookup_int(ip_int)

    def lookup_packed(self, packed_ip: bytes) -> Optional[str]:
        """Look up a 4-byte big-endian packed IPv4 address.

        Convenience wrapper used by the parser when it has already unpacked
        the raw bytes from the flow record.
        """
        if len(packed_ip) != 4:
            return None
        ip_int = struct.unpack('!I', packed_ip)[0]
        return self._lookup_int(ip_int)

    def _lookup_int(self, ip_int: int) -> Optional[str]:
        """Internal integer-keyed lookup."""
        node = self._root
        best_asn: Optional[str] = None
        for bit_pos in range(31, -1, -1):
            bit = (ip_int >> bit_pos) & 1
            node = node.children[bit]
            if node is None:
                break
            if node.asn is not None:
                best_asn = node.asn
        return best_asn

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------

    @property
    def prefix_count(self) -> int:
        """Number of CIDR prefixes currently loaded."""
        return self._prefix_count

    def all_asns(self) -> List[str]:
        """Return a sorted list of all distinct ASN values in the trie."""
        asns: List[str] = []
        self._collect_asns(self._root, asns)
        return sorted(set(asns))

    def _collect_asns(self, node: Optional[_TrieNode], out: List[str]) -> None:
        if node is None:
            return
        if node.asn is not None:
            out.append(node.asn)
        self._collect_asns(node.children[0], out)
        self._collect_asns(node.children[1], out)
