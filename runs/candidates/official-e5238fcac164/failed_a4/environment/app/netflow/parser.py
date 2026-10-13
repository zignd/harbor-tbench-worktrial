"""
NetFlow v9 binary packet parser.

Parses packet headers, template flowsets, and data flowsets according to
RFC 3954. Maintains a template cache so that data flowsets can be decoded
after the corresponding template flowset has been received.
"""

import struct
from typing import Dict, List, Optional, Tuple, Iterator
from .schema import (
    TEMPLATE_FLOWSET_ID, OPTIONS_FLOWSET_ID, DATA_FLOWSET_ID_MIN,
    PACKET_HEADER_SIZE, FLOWSET_HEADER_SIZE,
    TEMPLATE_RECORD_HEADER_SIZE, TEMPLATE_FIELD_SIZE,
    IN_BYTES, IPV4_SRC_ADDR,
)
from .utils import get_logger, unpack_uint16, unpack_uint32, unpack_ipv4

log = get_logger(__name__)


class TemplateField:
    """A single field definition within a NetFlow v9 template record."""
    __slots__ = ('field_type', 'field_length')

    def __init__(self, field_type: int, field_length: int):
        self.field_type = field_type
        self.field_length = field_length

    def __repr__(self) -> str:
        return f'TemplateField(type={self.field_type}, len={self.field_length})'


class Template:
    """
    A parsed NetFlow v9 template record.

    Attributes:
        template_id: The numeric ID of this template (>= 256).
        fields: Ordered list of TemplateField objects.
        record_length: Total byte length of one data record using this template.
    """

    def __init__(self, template_id: int, fields: List[TemplateField]):
        self.template_id = template_id
        self.fields = fields
        self.record_length = sum(f.field_length for f in fields)

    def field_offset(self, target_type: int) -> Optional[Tuple[int, int]]:
        """
        Return (byte_offset, byte_length) for the first field with the given
        field type, or None if the template does not contain that field.
        """
        offset = 0
        for field in self.fields:
            if field.field_type == target_type:
                return offset, field.field_length
            offset += field.field_length
        return None

    def __repr__(self) -> str:
        return (f'Template(id={self.template_id}, '
                f'fields={len(self.fields)}, '
                f'record_len={self.record_length})')


class FlowRecord:
    """
    A single decoded data flow record extracted from a data flowset.

    Attributes:
        template_id: ID of the template used to decode this record.
        src_ip: Source IPv4 address string (dotted-decimal), or None.
        in_bytes: Byte count for this flow, or None if field absent.
        raw: Raw bytes of this record.
    """
    __slots__ = ('template_id', 'src_ip', 'in_bytes', 'raw')

    def __init__(self, template_id: int, src_ip: Optional[str],
                 in_bytes: Optional[int], raw: bytes):
        self.template_id = template_id
        self.src_ip = src_ip
        self.in_bytes = in_bytes
        self.raw = raw

    def __repr__(self) -> str:
        return (f'FlowRecord(tmpl={self.template_id}, '
                f'src={self.src_ip}, bytes={self.in_bytes})')


class PacketHeader:
    """Parsed NetFlow v9 packet header."""
    __slots__ = ('version', 'count', 'sys_uptime', 'unix_secs',
                 'sequence', 'source_id')

    def __init__(self, version, count, sys_uptime, unix_secs, sequence, source_id):
        self.version = version
        self.count = count
        self.sys_uptime = sys_uptime
        self.unix_secs = unix_secs
        self.sequence = sequence
        self.source_id = source_id

    def __repr__(self) -> str:
        return (f'PacketHeader(ver={self.version}, count={self.count}, '
                f'seq={self.sequence})')


class NetFlowV9Parser:
    """
    Stateful NetFlow v9 parser.

    Maintains a template cache across calls to parse_packet() so that
    data flowsets received after their template definitions are decodable.
    A single instance should be reused across all packets in a logical
    export stream.
    """

    def __init__(self):
        # Maps template_id -> Template
        self.templates: Dict[int, Template] = {}
        self._packets_parsed = 0
        self._records_emitted = 0
        self._templates_seen = 0
        self._unknown_template_ids = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse_file(self, data: bytes) -> Iterator[FlowRecord]:
        """
        Parse all NetFlow v9 packets contained in *data* (a raw binary blob
        as typically stored in a capture file) and yield FlowRecord objects.

        Packets are assumed to be concatenated without any framing headers.
        Each packet boundary is found by summing flowset lengths (each
        flowset header carries its own byte length).
        """
        offset = 0
        while offset < len(data):
            if offset + PACKET_HEADER_SIZE > len(data):
                log.debug('Truncated packet header at offset %d', offset)
                break
            version = unpack_uint16(data, offset)
            count = unpack_uint16(data, offset + 2)
            sys_uptime = unpack_uint32(data, offset + 4)
            unix_secs = unpack_uint32(data, offset + 8)
            sequence = unpack_uint32(data, offset + 12)
            source_id = unpack_uint32(data, offset + 16)

            if version != 9:
                log.warning('Non-v9 packet (version=%d) at offset %d; stopping',
                            version, offset)
                break

            header = PacketHeader(version, count, sys_uptime, unix_secs,
                                  sequence, source_id)
            fs_offset = offset + PACKET_HEADER_SIZE

            # Walk flowsets to find where this packet ends
            pkt_end, records = self._walk_flowsets(data, fs_offset,
                                                    len(data), header)
            yield from records
            self._packets_parsed += 1
            offset = pkt_end

    def parse_packet(self, data: bytes) -> Iterator[FlowRecord]:
        """
        Parse a single NetFlow v9 UDP packet and yield FlowRecord objects.
        """
        if len(data) < PACKET_HEADER_SIZE:
            log.debug('Packet too short: %d bytes', len(data))
            return
        version = unpack_uint16(data, 0)
        count = unpack_uint16(data, 2)
        if version != 9:
            return
        sys_uptime = unpack_uint32(data, 4)
        unix_secs = unpack_uint32(data, 8)
        sequence = unpack_uint32(data, 12)
        source_id = unpack_uint32(data, 16)
        header = PacketHeader(version, count, sys_uptime, unix_secs,
                              sequence, source_id)
        _, records = self._walk_flowsets(data, PACKET_HEADER_SIZE,
                                         len(data), header)
        yield from records
        self._packets_parsed += 1

    def template_count(self) -> int:
        """Return the number of distinct templates currently cached."""
        return len(self.templates)

    def stats(self) -> dict:
        """Return a snapshot of parser statistics."""
        return {
            'packets_parsed': self._packets_parsed,
            'records_emitted': self._records_emitted,
            'templates_cached': len(self.templates),
            'templates_seen': self._templates_seen,
            'unknown_template_ids': len(self._unknown_template_ids),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _walk_flowsets(self, data: bytes, offset: int, limit: int,
                       header: PacketHeader) -> Tuple[int, list]:
        """
        Walk flowsets starting at *offset*, processing at most
        header.count flowsets or until *limit* is reached.
        Returns (new_offset, list_of_flow_records).
        """
        records = []
        flowsets_remaining = header.count
        while flowsets_remaining > 0 and offset + FLOWSET_HEADER_SIZE <= limit:
            if offset + 4 > len(data):
                break
            flowset_id = unpack_uint16(data, offset)
            flowset_length = unpack_uint16(data, offset + 2)
            if flowset_length < 4:
                log.debug('Invalid flowset length %d at offset %d',
                          flowset_length, offset)
                break
            flowset_data_start = offset + 4
            flowset_end = offset + flowset_length
            if flowset_end > len(data):
                flowset_end = len(data)

            if flowset_id == TEMPLATE_FLOWSET_ID:
                self._process_template_flowset(
                    data, flowset_data_start, flowset_end)
            elif flowset_id == OPTIONS_FLOWSET_ID:
                pass  # Options templates not used in settlement
            elif flowset_id >= DATA_FLOWSET_ID_MIN:
                for rec in self._process_data_flowset(
                        data, flowset_data_start, flowset_end, flowset_id):
                    records.append(rec)
            else:
                log.debug('Unknown flowset_id %d at offset %d',
                          flowset_id, offset)

            offset = flowset_end
            flowsets_remaining -= 1

        return offset, records

    def _process_template_flowset(self, data: bytes,
                                  offset: int, end: int) -> None:
        """Parse all template records within a template flowset."""
        while offset + TEMPLATE_RECORD_HEADER_SIZE <= end:
            template_id = unpack_uint16(data, offset)
            field_count = unpack_uint16(data, offset + 2)
            offset += TEMPLATE_RECORD_HEADER_SIZE

            if template_id == 0 or field_count == 0:
                break

            self._templates_seen += 1
            fields_end = offset + field_count * TEMPLATE_FIELD_SIZE
            if fields_end > end:
                log.debug('Template %d: field data truncated', template_id)
                break

            # If we have already seen this template ID, skip it so we do
            # not overwrite the cached layout with a re-exported copy.
            if template_id in self.templates:
                offset = fields_end
                continue

            fields: List[TemplateField] = []
            for _ in range(field_count):
                ftype = unpack_uint16(data, offset)
                flen = unpack_uint16(data, offset + 2)
                fields.append(TemplateField(ftype, flen))
                offset += TEMPLATE_FIELD_SIZE

            tmpl = Template(template_id, fields)
            self.templates[template_id] = tmpl
            log.debug('Cached template %d: %d fields, %d bytes/record',
                      template_id, len(fields), tmpl.record_length)

    def _process_data_flowset(self, data: bytes, offset: int, end: int,
                              flowset_id: int) -> Iterator[FlowRecord]:
        """Decode all flow records within a data flowset."""
        template = self.templates.get(flowset_id)
        if template is None:
            if flowset_id not in self._unknown_template_ids:
                log.debug('No template for flowset_id %d; skipping', flowset_id)
                self._unknown_template_ids.add(flowset_id)
            return

        rec_len = template.record_length
        if rec_len == 0:
            return

        src_info = template.field_offset(IPV4_SRC_ADDR)
        bytes_info = template.field_offset(IN_BYTES)

        while offset + rec_len <= end:
            raw = data[offset: offset + rec_len]

            src_ip: Optional[str] = None
            if src_info is not None:
                src_off, src_len = src_info
                if src_len == 4:
                    src_ip = unpack_ipv4(raw, src_off)

            in_bytes: Optional[int] = None
            if bytes_info is not None:
                b_off, b_len = bytes_info
                if b_len == 4:
                    in_bytes = unpack_uint32(raw, b_off)
                elif b_len == 2:
                    in_bytes = unpack_uint16(raw, b_off)
                elif b_len == 1:
                    in_bytes = raw[b_off]

            record = FlowRecord(flowset_id, src_ip, in_bytes, raw)
            self._records_emitted += 1
            yield record
            offset += rec_len
