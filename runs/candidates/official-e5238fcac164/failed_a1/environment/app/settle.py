#!/usr/bin/env python3
"""
settle.py - NetFlow Settlement Aggregator CLI.

Discovers NetFlow v9 binary files in the given data directory, decodes
flow records, attributes byte counts to counterparties via an IP-to-ASN
mapping table, and writes a per-counterparty settlement CSV.

Usage::

    python settle.py /app/data/
    python settle.py /app/data/ --output /tmp/settlement.csv

The output CSV has columns ``asn`` and ``bytes``.  Only ASNs with at
least one attributed byte appear in the output; ASNs with zero traffic
are omitted.
"""

import argparse
import os
import sys

# Ensure the package root is on sys.path when run directly.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from netflow.aggregator import run
from netflow.utils import get_logger

logger = get_logger('settle')


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description='Aggregate NetFlow v9 records into per-counterparty byte totals.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        'data_dir',
        help='Directory containing *.bin NetFlow capture files and asn_map.csv',
    )
    p.add_argument(
        '--output',
        default='settlement.csv',
        metavar='PATH',
        help='Output CSV path (default: %(default)s)',
    )
    p.add_argument(
        '--log-level',
        default='WARNING',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging verbosity (default: %(default)s)',
    )
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    import logging
    logging.getLogger('netflow').setLevel(getattr(logging, args.log_level))

    data_dir = os.path.abspath(args.data_dir)
    if not os.path.isdir(data_dir):
        logger.error('Data directory does not exist: %s', data_dir)
        sys.exit(1)

    asn_map_path = os.path.join(data_dir, 'asn_map.csv')
    if not os.path.isfile(asn_map_path):
        logger.error('ASN map not found: %s', asn_map_path)
        sys.exit(1)

    output_path = args.output
    output_dir = os.path.dirname(os.path.abspath(output_path))
    if not os.path.isdir(output_dir):
        logger.error('Output directory does not exist: %s', output_dir)
        sys.exit(1)

    run(data_dir, output_path)
    logger.info('Settlement written to %s', output_path)


if __name__ == '__main__':
    main()
