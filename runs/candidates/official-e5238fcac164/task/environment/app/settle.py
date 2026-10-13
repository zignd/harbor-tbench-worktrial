
"""
NetFlow v9 settlement entry point.

Usage:
    python /app/settle.py <data_directory>

Discovers all *.bin files in <data_directory> (sorted by filename),
parses NetFlow v9 records, maps each source IP to a counterparty ASN
using /app/data/asn_map.csv, classifies each flow by DSCP value using
/app/data/traffic_class_map.csv, and writes per-ASN per-class byte
totals to settlement.csv in the current working directory.

Output columns: asn, traffic_class, total_bytes
"""

import sys
import os
import csv
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from netflow.aggregator import FlowAggregator
from netflow.utils import get_logger

log = get_logger('settle')

OUTPUT_FILE = 'settlement.csv'
ASN_MAP_RELATIVE = 'asn_map.csv'
TC_MAP_RELATIVE = 'traffic_class_map.csv'


def find_data_file(data_dir: str, filename: str) -> str:
    candidates = [
        os.path.join(data_dir, filename),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', filename),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    raise FileNotFoundError(f'{filename} not found; tried: {candidates}')


def write_settlement(totals: dict, output_path: str) -> None:
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['asn', 'traffic_class', 'total_bytes'])
        for (asn, tc) in sorted(totals.keys()):
            writer.writerow([asn, tc, totals[(asn, tc)]])
    log.info('Wrote %d rows to %s', len(totals), output_path)


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
        asn_map_path = find_data_file(data_dir, ASN_MAP_RELATIVE)
        tc_map_path = find_data_file(data_dir, TC_MAP_RELATIVE)
    except FileNotFoundError as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(1)

    aggregator = FlowAggregator(asn_csv_path=asn_map_path, tc_csv_path=tc_map_path)
    totals = aggregator.process_directory(data_dir)

    if not totals:
        print('Warning: no byte totals produced; check input files.',
              file=sys.stderr)

    write_settlement(totals, OUTPUT_FILE)

    stats = aggregator.stats()
    print(f'Processed {stats.files_processed} file(s), '
          f'{stats.records_decoded} record(s), '
          f'{len(totals)} ASN/class row(s). '
          f'Output: {OUTPUT_FILE}')


if __name__ == '__main__':
    main()
