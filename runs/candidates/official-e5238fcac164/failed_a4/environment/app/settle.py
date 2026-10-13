"""
NetFlow v9 settlement entry point.

Usage:
    python /app/settle.py <data_directory>

Discovers all *.bin files in <data_directory> (sorted by filename),
parsing NetFlow v9 records, maps each source IP to a counterparty ASN
using /app/data/asn_map.csv, and writes per-ASN byte totals to
settlement.csv in the current working directory.

Output columns: asn, total_bytes
"""

import sys
import os
import csv
import logging

# Ensure /app is on the path so 'netflow' package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from netflow.aggregator import FlowAggregator
from netflow.utils import get_logger

log = get_logger('settle')

OUTPUT_FILE = 'settlement.csv'
ASN_MAP_RELATIVE = 'asn_map.csv'


def find_asn_map(data_dir: str) -> str:
    """Locate asn_map.csv: look in data_dir, then /app/data/."""
    candidates = [
        os.path.join(data_dir, ASN_MAP_RELATIVE),
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'data', ASN_MAP_RELATIVE),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    raise FileNotFoundError(
        f'asn_map.csv not found; tried: {candidates}'
    )


def write_settlement(totals: dict, output_path: str) -> None:
    """Write per-ASN byte totals to a CSV file."""
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['asn', 'total_bytes'])
        for asn in sorted(totals.keys()):
            writer.writerow([asn, totals[asn]])
    log.info('Wrote %d ASN rows to %s', len(totals), output_path)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    if len(argv) != 1:
        print(f'Usage: python {sys.argv[0]} <data_directory>', file=sys.stderr)
        sys.exit(1)

    data_dir = os.path.abspath(argv[0])
    if not os.path.isdir(data_dir):
        print(f'Error: {data_dir!r} is not a directory', file=sys.stderr)
        sys.exit(1)

    try:
        asn_map_path = find_asn_map(data_dir)
    except FileNotFoundError as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(1)

    aggregator = FlowAggregator(asn_csv_path=asn_map_path)
    totals = aggregator.process_directory(data_dir)

    if not totals:
        print('Warning: no byte totals produced; check input files.',
              file=sys.stderr)

    write_settlement(totals, OUTPUT_FILE)

    stats = aggregator.stats()
    print(f'Processed {stats.files_processed} file(s), '
          f'{stats.records_decoded} record(s), '
          f'{len(totals)} ASN(s). '
          f'Output: {OUTPUT_FILE}')


if __name__ == '__main__':
    main()
