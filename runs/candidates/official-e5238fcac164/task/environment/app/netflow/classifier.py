
"""
Traffic class classifier for NetFlow settlement.

Maps a DSCP value (the upper 6 bits of the IP ToS byte) to a named
traffic class string using a CSV lookup table. Used by the aggregator
to produce per-counterparty per-class byte totals in settlement.csv.

CSV format (columns: dscp,traffic_class):
    0,default
    46,expedited-forwarding
    34,assured-forwarding-high
    18,assured-forwarding-medium
    10,assured-forwarding-low
    8,class-selector-1
"""

import csv
import struct
import socket
from typing import Dict, Optional
from .utils import get_logger

log = get_logger(__name__)

DEFAULT_CLASS = 'default'


def dscp_from_tos(tos_byte: int) -> int:
    """
    Extract the 6-bit DSCP value from an IP ToS byte.
    The DSCP occupies bits 7-2 (the upper six bits).
    """
    return (tos_byte >> 2) & 0x3F


class TrafficClassifier:
    """
    Lookup table mapping DSCP values to traffic class names.

    Loaded from a CSV file with columns: dscp, traffic_class.
    DSCP values not found in the table resolve to DEFAULT_CLASS.
    """

    def __init__(self, csv_path: str):
        self._map: Dict[int, str] = {}
        self._load(csv_path)

    def _load(self, csv_path: str) -> None:
        loaded = 0
        try:
            with open(csv_path, newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        dscp = int(row['dscp'].strip())
                        tc = row['traffic_class'].strip()
                        self._map[dscp] = tc
                        loaded += 1
                    except (KeyError, ValueError) as exc:
                        log.warning('Skipping bad traffic_class row %r: %s', row, exc)
        except FileNotFoundError:
            log.warning('traffic_class_map.csv not found at %s; all flows -> default', csv_path)
        log.info('TrafficClassifier: loaded %d DSCP mappings from %s', loaded, csv_path)

    def classify(self, tos_byte: int) -> str:
        """
        Return the traffic class name for a given ToS byte value.
        Extracts the DSCP field and looks it up in the table.
        Returns DEFAULT_CLASS if the DSCP is not mapped.
        """
        dscp = dscp_from_tos(tos_byte)
        return self._map.get(dscp, DEFAULT_CLASS)

    def classify_dscp(self, dscp: int) -> str:
        """
        Return the traffic class name for a raw 6-bit DSCP value.
        """
        return self._map.get(dscp & 0x3F, DEFAULT_CLASS)

    def all_classes(self):
        """
        Return a sorted list of all distinct traffic class names in the table,
        including the default class.
        """
        classes = set(self._map.values())
        classes.add(DEFAULT_CLASS)
        return sorted(classes)

    def dscp_for_class(self, class_name: str):
        """
        Return all DSCP values that map to the given traffic class.
        """
        return [k for k, v in self._map.items() if v == class_name]

    def __repr__(self) -> str:
        return f'TrafficClassifier({len(self._map)} DSCP entries)'
