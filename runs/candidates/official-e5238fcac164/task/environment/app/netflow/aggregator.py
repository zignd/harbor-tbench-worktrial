
"""
Flow aggregator: accumulates per-ASN per-traffic-class byte totals
from NetFlow v9 records across multiple binary files.
"""

import os
from typing import Dict, List, Tuple
from .parser import NetFlowV9Parser
from .asn_lookup import CachingASNLookup
from .classifier import TrafficClassifier, DEFAULT_CLASS
from .utils import get_logger, pretty_bytes

log = get_logger(__name__)

# Key type for per-counterparty per-class totals
AggKey = Tuple[str, str]  # (asn, traffic_class)


class AggregationStats:
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
    per-ASN per-traffic-class byte totals.

    Usage:
        agg = FlowAggregator(
            asn_csv_path='/app/data/asn_map.csv',
            tc_csv_path='/app/data/traffic_class_map.csv',
        )
        totals = agg.process_directory('/app/data/')
        # totals -> {('AS64501', 'expedited-forwarding'): 1234567, ...}
    """

    def __init__(self, asn_csv_path: str, tc_csv_path: str):
        self._asn_lookup = CachingASNLookup(asn_csv_path)
        self._classifier = TrafficClassifier(tc_csv_path)
        self._totals: Dict[AggKey, int] = {}
        self._stats = AggregationStats()

    def process_directory(self, directory: str) -> Dict[AggKey, int]:
        """
        Discover all *.bin files in *directory*, sort them by filename,
        and process each in order. Returns accumulated per-ASN per-class
        byte totals as a dict mapping (asn, traffic_class) -> total_bytes.
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

    def process_files(self, filepaths: List[str]) -> Dict[AggKey, int]:
        for filepath in filepaths:
            self._process_file(filepath)
        return dict(self._totals)

    def totals(self) -> Dict[AggKey, int]:
        return dict(self._totals)

    def stats(self) -> AggregationStats:
        return self._stats

    def reset(self) -> None:
        self._totals.clear()
        self._stats = AggregationStats()
        self._parser = None

    def _process_file(self, filepath: str) -> None:
        """
        Parse one binary capture file and accumulate its flow bytes into
        the per-ASN per-class totals.
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
        if record.src_ip is None:
            self._stats.records_skipped_no_ip += 1
            return
        if record.in_bytes is None:
            self._stats.records_skipped_no_bytes += 1
            return

        asn = self._asn_lookup.lookup(record.src_ip)
        if asn is None:
            self._stats.records_skipped_no_asn += 1
            log.debug('No ASN for src_ip %s; skipping', record.src_ip)
            return

        tos = record.tos if record.tos is not None else 0
        tc = self._classifier.classify(tos)

        key = (asn, tc)
        self._totals[key] = self._totals.get(key, 0) + record.in_bytes
        self._stats.total_bytes_attributed += record.in_bytes

    def _format_totals_report(self) -> str:
        lines = ['Per-ASN Per-Class Byte Totals:']
        for (asn, tc) in sorted(self._totals):
            nb = self._totals[(asn, tc)]
            lines.append(f'  {asn}/{tc}: {pretty_bytes(nb)} ({nb:,} bytes)')
        return '\n'.join(lines)
