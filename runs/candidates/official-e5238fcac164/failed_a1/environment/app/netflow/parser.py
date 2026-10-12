"""
parser.py - NetFlow v9 binary packet parser.

Handles template FlowSets, data FlowSets, and Options Template FlowSets
following RFC 3954.  The parser maintains an internal template cache that
maps template IDs to their field definitions so that subsequent data
FlowSets can be decoded.

Typical usage::

    parser = Parser()
    records = parser.parse_file('/app/data/flows_001.bin')
    for rec in records:
        src_ip = rec.get('IPV4_SRC_ADDR')
        in_bytes = rec.get('IN_BYTES', 0)

The parser is intentionally stateful so that template definitions seen in
one file are available when parsing subsequent files passed to the same
instance.  The caller controls whether to share or reset the parser between
files.
"""

import socket
import struct
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Tuple

from netflow import schema
from netflow.utils import (
    get_logger,
    int_to_ip,
    read_binary_file,
    bytes_to_uint,
)

logger = get_logger('parser')

# NetFlow v9 packet header is always 20 bytes.
_HEADER_LEN = 20
# Each flowset starts with a 4-byte preamble (flowset_id + length).
_FLOWSET_HDR_LEN = 4


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FieldDef:
    """A single field definition within a template."""
    type_id: int     # RFC 3954 field type identifier
    length: int      # field width in bytes

    @property
    def name(self) -> str:
        """Human-readable field name, or 'FIELD_<n>' for unknown types."""
        return schema.FIELD_NAMES.get(self.type_id, f'FIELD_{self.type_id}')


@dataclass
class Template:
    """A decoded NetFlow v9 template (template FlowSet entry)."""
    template_id: int
    fields: List[FieldDef] = field(default_factory=list)

    @property
    def record_length(self) -> int:
        """Total byte width of one data record using this template."""
        return sum(f.length for f in self.fields)


@dataclass
class FlowRecord:
    """A single decoded flow record."""
    template_id: int
    fields: Dict[str, int]   # field_name -> integer value

    def get(self, field_name: str, default: int = 0) -> int:
        """Return the value of *field_name*, or *default* if absent."""
        return self.fields.get(field_name, default)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class Parser:
    """Stateful NetFlow v9 binary parser.

    The parser accumulates template definitions across successive calls to
    :meth:`parse_file` or :meth:`parse_bytes`.  Reset the instance (or
    create a new one) to start fresh.
    """

    def __init__(self):
        # template_id -> Template
        self.templates: Dict[int, Template] = {}
        self._packets_seen = 0
        self._records_decoded = 0
        self._templates_seen = 0

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def parse_file(self, path: str) -> List[FlowRecord]:
        """Parse all NetFlow v9 packets from the binary file at *path*.

        Returns a list of :class:`FlowRecord` objects decoded from data
        FlowSets in the file.  Template FlowSets are consumed and used to
        update the internal cache but do not produce FlowRecord objects.
        """
        data = read_binary_file(path)
        logger.debug('Parsing %s (%d bytes)', path, len(data))
        return self.parse_bytes(data, source=path)

    def parse_bytes(self, data: bytes, source: str = '<bytes>') -> List[FlowRecord]:
        """Parse all NetFlow v9 packets from *data*.

        A single file may contain multiple back-to-back NetFlow v9 packets;
        this method consumes all of them.
        """
        records: List[FlowRecord] = []
        offset = 0
        total = len(data)
        while offset < total:
            if offset + _HEADER_LEN > total:
                logger.debug('%s: %d trailing bytes, stopping', source, total - offset)
                break
            pkt_records, consumed = self._parse_packet(data, offset, source)
            if consumed <= 0:
                logger.warning('%s: zero-length packet at offset %d, stopping', source, offset)
                break
            records.extend(pkt_records)
            offset += consumed
            self._packets_seen += 1
        logger.debug('%s: decoded %d records from %d packets', source, len(records), self._packets_seen)
        return records

    # ------------------------------------------------------------------
    # Packet-level parsing
    # ------------------------------------------------------------------

    def _parse_packet(self, data: bytes, base: int, source: str) -> Tuple[List[FlowRecord], int]:
        """Parse one NetFlow v9 packet starting at *base*.

        Returns (records, bytes_consumed).
        """
        if base + _HEADER_LEN > len(data):
            return [], 0

        version, count, uptime, unix_secs, seq_num, source_id = struct.unpack_from(
            '!HHIIII', data, base
        )
        if version != schema.NETFLOW_V9_VERSION:
            logger.warning(
                '%s: unexpected version %d at offset %d (expected 9)',
                source, version, base
            )
            return [], _HEADER_LEN

        logger.debug(
            '%s: packet seq=%d count=%d uptime=%d src_id=%d',
            source, seq_num, count, uptime, source_id
        )

        offset = base + _HEADER_LEN
        end = len(data)
        records: List[FlowRecord] = []
        flowsets_parsed = 0

        # We iterate until we have parsed `count` FlowSets or run out of
        # data.  RFC 3954 counts FlowSets, not individual records.
        while flowsets_parsed < count and offset + _FLOWSET_HDR_LEN <= end:
            flowset_id, flowset_len = struct.unpack_from('!HH', data, offset)
            if flowset_len < _FLOWSET_HDR_LEN:
                logger.warning(
                    '%s: flowset at offset %d has invalid length %d, stopping packet',
                    source, offset, flowset_len
                )
                break
            flowset_end = offset + flowset_len
            if flowset_end > end:
                logger.warning(
                    '%s: flowset at offset %d extends beyond data (%d > %d)',
                    source, offset, flowset_end, end
                )
                break

            if flowset_id == schema.FLOWSET_ID_TEMPLATE:
                self._parse_template_flowset(data, offset + _FLOWSET_HDR_LEN, flowset_end, source)
            elif flowset_id == schema.FLOWSET_ID_OPTIONS:
                # Options Template FlowSets are not used for settlement;
                # we skip them but still advance the offset.
                logger.debug('%s: skipping Options Template FlowSet at offset %d', source, offset)
            elif flowset_id >= schema.FLOWSET_ID_DATA_MIN:
                recs = self._parse_data_flowset(data, offset + _FLOWSET_HDR_LEN, flowset_end, flowset_id, source)
                records.extend(recs)
            else:
                logger.warning('%s: unknown flowset_id %d at offset %d', source, flowset_id, offset)

            offset = flowset_end
            flowsets_parsed += 1

        bytes_consumed = offset - base
        return records, bytes_consumed

    # ------------------------------------------------------------------
    # Template FlowSet parsing
    # ------------------------------------------------------------------

    def _parse_template_flowset(self, data: bytes, start: int, end: int, source: str) -> None:
        """Parse a Template FlowSet body and update the template cache."""
        offset = start
        while offset + 4 <= end:
            template_id, field_count = struct.unpack_from('!HH', data, offset)
            offset += 4

            if template_id == 0:
                # Padding — skip.
                break

            fields: List[FieldDef] = []
            for _ in range(field_count):
                if offset + 4 > end:
                    logger.warning(
                        '%s: template %d field definition truncated at offset %d',
                        source, template_id, offset
                    )
                    break
                field_type, field_len = struct.unpack_from('!HH', data, offset)
                offset += 4
                fields.append(FieldDef(type_id=field_type, length=field_len))

            if len(fields) != field_count:
                logger.warning(
                    '%s: template %d: expected %d fields, got %d',
                    source, template_id, field_count, len(fields)
                )
                continue

            # Only cache this template if we haven't seen it before.
            # Re-exported templates with the same ID are ignored.
            if template_id in self.templates:
                continue

            tpl = Template(template_id=template_id, fields=fields)
            self.templates[template_id] = tpl
            self._templates_seen += 1
            logger.debug(
                '%s: cached template %d with %d fields (%d bytes/record)',
                source, template_id, len(fields), tpl.record_length
            )

    # ------------------------------------------------------------------
    # Data FlowSet parsing
    # ------------------------------------------------------------------

    def _parse_data_flowset(self, data: bytes, start: int, end: int,
                             template_id: int, source: str) -> List[FlowRecord]:
        """Decode all flow records from a data FlowSet body.

        Returns a (possibly empty) list of :class:`FlowRecord` objects.
        If the template for *template_id* is not in the cache the FlowSet
        is silently skipped — this can happen when packets arrive out of
        order relative to the template export.
        """
        tpl = self.templates.get(template_id)
        if tpl is None:
            logger.debug(
                '%s: no template for flowset id %d, skipping %d bytes',
                source, template_id, end - start
            )
            return []

        rec_len = tpl.record_length
        if rec_len == 0:
            logger.warning('%s: template %d has zero-length records', source, template_id)
            return []

        records: List[FlowRecord] = []
        offset = start
        while offset + rec_len <= end:
            rec_fields: Dict[str, int] = {}
            field_offset = offset
            for fdef in tpl.fields:
                raw = data[field_offset: field_offset + fdef.length]
                value = bytes_to_uint(raw, big_endian=True)
                # For IPv4 addresses store both the integer and the
                # dotted-decimal string so callers can use either form.
                if fdef.type_id == schema.IPV4_SRC_ADDR and fdef.length == 4:
                    rec_fields['IPV4_SRC_ADDR'] = value
                    rec_fields['IPV4_SRC_ADDR_STR'] = int_to_ip(value)
                elif fdef.type_id == schema.IPV4_DST_ADDR and fdef.length == 4:
                    rec_fields['IPV4_DST_ADDR'] = value
                    rec_fields['IPV4_DST_ADDR_STR'] = int_to_ip(value)
                else:
                    name = fdef.name
                    rec_fields[name] = value
                field_offset += fdef.length

            records.append(FlowRecord(template_id=template_id, fields=rec_fields))
            offset += rec_len
            self._records_decoded += 1

        # Any remaining bytes are padding to align the FlowSet to a 4-byte
        # boundary; they are intentionally ignored.
        return records

    # ------------------------------------------------------------------
    # Diagnostic helpers
    # ------------------------------------------------------------------

    @property
    def packets_seen(self) -> int:
        return self._packets_seen

    @property
    def records_decoded(self) -> int:
        return self._records_decoded

    @property
    def templates_seen(self) -> int:
        return self._templates_seen

    def reset_stats(self) -> None:
        """Reset packet/record counters without clearing the template cache."""
        self._packets_seen = 0
        self._records_decoded = 0
        self._templates_seen = 0

    def dump_templates(self) -> str:
        """Return a human-readable summary of cached templates."""
        lines = [f'Templates cached: {len(self.templates)}']
        for tid, tpl in sorted(self.templates.items()):
            field_summary = ', '.join(
                f'{f.name}({f.length}B)' for f in tpl.fields
            )
            lines.append(f'  Template {tid}: {field_summary}')
        return '\n'.join(lines)
