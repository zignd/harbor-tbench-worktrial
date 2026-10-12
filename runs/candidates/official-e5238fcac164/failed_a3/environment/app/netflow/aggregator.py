"""
aggregator.py - Per-ASN byte-count accumulator for NetFlow settlement.

The Aggregator orchestrates file discovery, parsing, IP-to-ASN resolution,
and CSV output.  It is the primary entry point used by settle.py.

Typical usage::

    agg = Aggregator('/app/data/asn_map.csv')
    agg.process_directory('/app/data')
    agg.write_csv('settlement.csv')
"""

import csv
import os
from typing import Dict, List, Optional

from netflow.asn_lookup import AsnLookup
from netflow.parser import Parser
from netflow.utils import get_logger

logger = get_logger('aggregator')


class Aggregator:
    """Accumulates per-ASN IN_BYTES totals from NetFlow v9 binary files.

    The class loads the ASN mapping table once at construction time and
    then processes one or more directories of binary capture files.
    Results are accumulated across successive calls to
    :meth:`process_directory` until :meth:`reset` is called.
    """

    def __init__(self, asn_map_path: str):
        self._lut = AsnLookup()
        self._lut.load_csv(asn_map_path)
        self._totals: Dict[str, int] = {}
        self._files_processed = 0
        self._records_attributed = 0
        self._records_unmatched = 0

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    def process_directory(self, data_dir: str) -> Dict[str, int]:
        """Discover and parse all *.bin files in *data_dir*.

        Files are processed in sorted filename order so that template
        definitions exported in earlier files (by name) are available
        when parsing later files.

        Returns the cumulative per-ASN byte totals after this call.
        """
        bin_files = sorted(
            f for f in os.listdir(data_dir) if f.endswith('.bin')
        )
        if not bin_files:
            logger.warning('No .bin files found in %s', data_dir)
            return dict(self._totals)

        logger.info('Processing %d files from %s', len(bin_files), data_dir)

        for filename in bin_files:
            filepath = os.path.join(data_dir, filename)
            logger.info('Parsing %s', filepath)

            # Create a fresh parser for each file so that processing
            # remains isolated between capture files.
            parser = Parser()

            try:
                records = parser.parse_file(filepath)
            except OSError as exc:
                logger.error('Failed to read %s: %s', filepath, exc)
                continue

            self._attribute_records(records, filename)
            self._files_processed += 1
            logger.info(
                '%s: %d records, %d attributed',
                filename, len(records),
                sum(1 for r in records
                    if r.get('IPV4_SRC_ADDR_STR') and
                    self._lut.lookup(r.get('IPV4_SRC_ADDR_STR', '')) is not None)
            )

        return dict(self._totals)

    def _attribute_records(self, records, source: str) -> None:
        """Attribute IN_BYTES from each record to the matching ASN."""
        for rec in records:
            src_ip = rec.fields.get('IPV4_SRC_ADDR_STR')
            if not src_ip:
                self._records_unmatched += 1
                continue

            asn = self._lut.lookup(src_ip)
            if asn is None:
                self._records_unmatched += 1
                logger.debug('No ASN for src_ip=%s in %s', src_ip, source)
                continue

            in_bytes = rec.get('IN_BYTES', 0)
            self._totals[asn] = self._totals.get(asn, 0) + in_bytes
            self._records_attributed += 1

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def get_totals(self) -> Dict[str, int]:
        """Return a copy of the current per-ASN byte totals."""
        return dict(self._totals)

    def write_csv(self, output_path: str) -> None:
        """Write per-ASN totals to a CSV file at *output_path*.

        The output has two columns: ``asn`` and ``bytes``.  Rows are
        sorted by ASN for deterministic output.
        """
        rows = sorted(self._totals.items())
        with open(output_path, 'w', newline='') as fh:
            writer = csv.writer(fh)
            writer.writerow(['asn', 'bytes'])
            for asn, total in rows:
                writer.writerow([asn, total])
        logger.info('Wrote %d ASN rows to %s', len(rows), output_path)

    def reset(self) -> None:
        """Clear accumulated totals and counters (keeps the ASN table)."""
        self._totals = {}
        self._files_processed = 0
        self._records_attributed = 0
        self._records_unmatched = 0

    # ------------------------------------------------------------------
    # Diagnostic helpers
    # ------------------------------------------------------------------

    @property
    def files_processed(self) -> int:
        return self._files_processed

    @property
    def records_attributed(self) -> int:
        return self._records_attributed

    @property
    def records_unmatched(self) -> int:
        return self._records_unmatched


def run(data_dir: str, output_path: str) -> None:
    """Convenience function used by settle.py.

    Locates the ASN map inside *data_dir*, runs the aggregator, and
    writes the settlement CSV to *output_path*.
    """
    asn_map = os.path.join(data_dir, 'asn_map.csv')
    agg = Aggregator(asn_map)
    agg.process_directory(data_dir)
    agg.write_csv(output_path)
    logger.info(
        'Settlement complete: %d ASNs, %d attributed records, %d unmatched',
        len(agg.get_totals()),
        agg.records_attributed,
        agg.records_unmatched,
    )
