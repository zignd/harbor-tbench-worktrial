"""
Per-ASN byte-count aggregator for NetFlow v9 settlement.

Receives FlowRecord objects from the parser and accumulates the IN_BYTES
field into per-counterparty totals keyed by ASN ID.  The ASN for each
record is resolved by looking up the source IP in the ASN mapping table.
"""

import os
import csv
from typing import Dict, List, Optional
from .parser import NetFlowV9Parser
from .asn_lookup import CachingASNLookup
from .utils import get_logger, pretty_bytes

log = get_logger(__name__)

UNKNOWN_ASN = 'UNKNOWN'


class AggregationStats:
    """Counters collected during a single aggregation run."""

    def __init__(self):
        self.files_processed: int = 0
        self.records_decoded: int = 0
        self.records_skipped_no_ip: int = 0
        self.records_skipped_no_bytes: int = 0
        self.records_skipped_no_asn: int = 0
        self.total_bytes_attributed: int = 0

    def __repr__(self) -> str:
        return (
            f'AggregationStats(files={self.files_processed}, '
            f'records={self.records_decoded}, '
            f'bytes={pretty_bytes(self.total_bytes_attributed)})'
        )


class FlowAggregator:
    """
    Aggregates NetFlow v9 records from multiple binary files into
    per-ASN byte totals.

    Usage:
        agg = FlowAggregator(asn_csv_path='/app/data/asn_map.csv')
        totals = agg.process_directory('/app/data/')
        # totals -> {'AS64501': 1234567, 'AS64502': 987654, ...}
    """

    def __init__(self, asn_csv_path: str):
        self._asn_lookup = CachingASNLookup(asn_csv_path)
        self._totals: Dict[str, int] = {}
        self._stats = AggregationStats()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_directory(self, directory: str) -> Dict[str, int]:
        """
        Discover all *.bin files in *directory*, sort them by filename,
        and process each in order.  Returns the accumulated per-ASN
        byte totals as a dict mapping ASN ID -> total bytes.
        """
        bin_files = sorted(
            f for f in os.listdir(directory) if f.endswith('.bin')
        )
        if not bin_files:
            log.warning('No .bin files found in %s', directory)
            return {}

        log.info('Processing %d file(s) from %s', len(bin_files), directory)

        for filename in bin_files:
            filepath = os.path.join(directory, filename)
            self._process_file(filepath)

        return dict(self._totals)

    def process_files(self, filepaths: List[str]) -> Dict[str, int]:
        """
        Process an explicit ordered list of binary file paths.
        Returns accumulated per-ASN byte totals.
        """
        for filepath in filepaths:
            self._process_file(filepath)
        return dict(self._totals)

    def totals(self) -> Dict[str, int]:
        """Return current per-ASN byte totals without processing new files."""
        return dict(self._totals)

    def stats(self) -> AggregationStats:
        """Return aggregation statistics."""
        return self._stats

    def reset(self) -> None:
        """Clear accumulated totals and statistics."""
        self._totals.clear()
        self._stats = AggregationStats()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _process_file(self, filepath: str) -> None:
        """
        Parse one binary capture file and accumulate its flow bytes into
        the per-ASN totals.
        """
        log.info('Processing file: %s', filepath)
        # Create a fresh parser for each file so memory stays bounded.
        parser = NetFlowV9Parser()

        try:
            with open(filepath, 'rb') as f:
                data = f.read()
        except OSError as exc:
            log.error('Cannot read %s: %s', filepath, exc)
            return

        records = 0
        for record in parser.parse_file(data):
            records += 1
            self._attribute_record(record)

        self._stats.files_processed += 1
        self._stats.records_decoded += records
        log.info('  %s: decoded %d records', filepath, records)

    def _attribute_record(self, record) -> None:
        """
        Resolve the ASN for a FlowRecord's source IP and add its byte count
        to the corresponding per-ASN total.
        """
        if record.src_ip is None:
            self._stats.records_skipped_no_ip += 1
            return
        if record.in_bytes is None:
            self._stats.records_skipped_no_bytes += 1
            return

        asn = self._asn_lookup.lookup(record.src_ip)
        if asn is None:
            self._stats.records_skipped_no_asn += 1
            log.debug('No ASN for src_ip %s; skipping record', record.src_ip)
            return

        self._totals[asn] = self._totals.get(asn, 0) + record.in_bytes
        self._stats.total_bytes_attributed += record.in_bytes

    def _format_totals_report(self) -> str:
        """Return a human-readable summary of per-ASN totals."""
        lines = ['Per-ASN Byte Totals:']
        for asn in sorted(self._totals):
            lines.append(f'  {asn}: {pretty_bytes(self._totals[asn])} '
                         f'({self._totals[asn]:,} bytes)')
        return '\n'.join(lines)
