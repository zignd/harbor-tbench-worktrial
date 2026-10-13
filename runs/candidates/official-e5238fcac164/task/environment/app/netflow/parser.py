
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
    IN_BYTES, IPV4_SRC_ADDR, SRC_TOS,
)
from .utils import get_logger, unpack_uint16, unpack_uint32, unpack_ipv4

log = get_logger(__name__)


class TemplateField:
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
        template_id: The numeric ID of this template.
        fields: Ordered list of TemplateField objects.
        record_length: Total byte length of one data record.
    """

    def __init__(self, template_id: int, fields: List[TemplateField]):
        self.template_id = template_id
        self.fields = fields
        self.record_length = sum(f.field_length for f in fields)

    def field_offset(self, target_type: int) -> Optional[Tuple[int, int]]:
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
    A single decoded data flow record.

    Attributes:
        template_id: ID of the template used to decode this record.
        src_ip: Source IPv4 address string, or None.
        in_bytes: Byte count for this flow, or None.
        tos: IP ToS byte (DSCP in upper 6 bits), or None.
        raw: Raw bytes of this record.
    """
    __slots__ = ('template_id', 'src_ip', 'in_bytes', 'tos', 'raw')

    def __init__(self, template_id: int, src_ip: Optional[str],
                 in_bytes: Optional[int], tos: Optional[int], raw: bytes):
        self.template_id = template_id
        self.src_ip = src_ip
        self.in_bytes = in_bytes
        self.tos = tos
        self.raw = raw

    def __repr__(self) -> str:
        return (f'FlowRecord(tmpl={self.template_id}, '
                f'src={self.src_ip}, bytes={self.in_bytes}, tos={self.tos})')


class PacketHeader:
    __slots__ = ('version', 'count', 'sys_uptime', 'unix_secs',
                 'sequence', 'source_id')

    def __init__(self, version, count, sys_uptime, unix_secs, sequence, source_id):
        self.version = version
        self.count = count
        self.sys_uptime = sys_uptime
        self.unix_secs = unix_secs
        self.sequence = sequence
        self.source_id = source_id


class NetFlowV9Parser:
    """
    Stateful NetFlow v9 parser.

    Maintains a template cache across calls to parse_packet() so that
    data flowsets received after their template definitions are decodable.
    A single instance should be reused across all packets in a logical
    export stream.
    """

    def __init__(self):
        self.templates: Dict[int, Template] = {}
        self._packets_parsed = 0
        self._records_emitted = 0
        self._templates_seen = 0
        self._unknown_template_ids = set()

    def parse_file(self, data: bytes) -> Iterator[FlowRecord]:
        """
        Parse all NetFlow v9 packets in *data* and yield FlowRecord objects.
        Packets are assumed to be concatenated without framing headers.
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
                log.warning('Non-v9 packet at offset %d; stopping', offset)
                break

            header = PacketHeader(version, count, sys_uptime, unix_secs,
                                  sequence, source_id)
            fs_offset = offset + PACKET_HEADER_SIZE
            pkt_end, records = self._walk_flowsets(data, fs_offset,
                                                    len(data), header)
            yield from records
            self._packets_parsed += 1
            offset = pkt_end

    def parse_packet(self, data: bytes) -> Iterator[FlowRecord]:
        if len(data) < PACKET_HEADER_SIZE:
            return
        version = unpack_uint16(data, 0)
        if version != 9:
            return
        count = unpack_uint16(data, 2)
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
        return len(self.templates)

    def stats(self) -> dict:
        return {
            'packets_parsed': self._packets_parsed,
            'records_emitted': self._records_emitted,
            'templates_cached': len(self.templates),
            'templates_seen': self._templates_seen,
            'unknown_template_ids': sorted(self._unknown_template_ids),
        }

    def _walk_flowsets(self, data: bytes, offset: int, limit: int,
                       header: PacketHeader):
        records = []
        flowsets_processed = 0
        while offset + FLOWSET_HEADER_SIZE <= limit:
            if offset + FLOWSET_HEADER_SIZE > len(data):
                break
            flowset_id = unpack_uint16(data, offset)
            flowset_length = unpack_uint16(data, offset + 2)
            if flowset_length < FLOWSET_HEADER_SIZE:
                log.warning('Malformed flowset length %d at offset %d',
                            flowset_length, offset)
                break
            flowset_end = offset + flowset_length
            if flowset_end > len(data):
                log.debug('Flowset extends beyond data at offset %d', offset)
                break
            body_offset = offset + FLOWSET_HEADER_SIZE
            if flowset_id == TEMPLATE_FLOWSET_ID:
                self._parse_template_flowset(data, body_offset, flowset_end)
            elif flowset_id == OPTIONS_FLOWSET_ID:
                log.debug('Options flowset at offset %d (skipped)', offset)
            elif flowset_id >= DATA_FLOWSET_ID_MIN:
                recs = list(self._parse_data_flowset(
                    data, body_offset, flowset_end, flowset_id))
                records.extend(recs)
            else:
                log.warning('Unknown flowset ID %d at offset %d',
                            flowset_id, offset)
            flowsets_processed += 1
            offset = flowset_end
        return offset, iter(records)

    def _parse_template_flowset(self, data: bytes, offset: int,
                                 end: int) -> None:
        while offset + TEMPLATE_RECORD_HEADER_SIZE <= end:
            template_id = unpack_uint16(data, offset)
            field_count = unpack_uint16(data, offset + 2)
            offset += TEMPLATE_RECORD_HEADER_SIZE
            if field_count == 0:
                continue
            fields_end = offset + field_count * TEMPLATE_FIELD_SIZE
            if fields_end > end:
                log.debug('Template record extends beyond flowset')
                break
            # If we have already seen this template ID, skip it so we do
            # not overwrite the cached layout with a re-exported copy.
            if template_id in self.templates:
                offset = fields_end
                continue
            fields = []
            for _ in range(field_count):
                ftype = unpack_uint16(data, offset)
                flen = unpack_uint16(data, offset + 2)
                fields.append(TemplateField(ftype, flen))
                offset += TEMPLATE_FIELD_SIZE
            tmpl = Template(template_id, fields)
            self.templates[template_id] = tmpl
            self._templates_seen += 1
            log.debug('Cached template %d (%d fields, %d bytes/rec)',
                      template_id, len(fields), tmpl.record_length)

    def _parse_data_flowset(self, data: bytes, offset: int, end: int,
                             template_id: int) -> Iterator[FlowRecord]:
        tmpl = self.templates.get(template_id)
        if tmpl is None:
            self._unknown_template_ids.add(template_id)
            log.debug('No template for flowset ID %d; skipping', template_id)
            return
        rec_len = tmpl.record_length
        if rec_len == 0:
            return
        src_info = tmpl.field_offset(IPV4_SRC_ADDR)
        bytes_info = tmpl.field_offset(IN_BYTES)
        tos_info = tmpl.field_offset(SRC_TOS)
        while offset + rec_len <= end:
            raw = data[offset: offset + rec_len]
            src_ip = None
            if src_info:
                o, l = src_info
                if l == 4:
                    src_ip = unpack_ipv4(raw, o)
            in_bytes = None
            if bytes_info:
                o, l = bytes_info
                if l == 4:
                    in_bytes = unpack_uint32(raw, o)
                elif l == 2:
                    in_bytes = unpack_uint16(raw, o)
                elif l == 8:
                    import struct as _s
                    in_bytes = _s.unpack_from('>Q', raw, o)[0]
            tos = None
            if tos_info:
                o, l = tos_info
                if l >= 1:
                    tos = raw[o] & 0xFF
            rec = FlowRecord(template_id, src_ip, in_bytes, tos, raw)
            self._records_emitted += 1
            yield rec
            offset += rec_len
