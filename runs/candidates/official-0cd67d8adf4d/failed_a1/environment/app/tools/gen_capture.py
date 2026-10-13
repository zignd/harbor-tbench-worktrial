#!/usr/bin/env python3
"""Generate synthetic NetFlow v9 pcap files for testing."""
import struct
import socket
import argparse
import json
import sys
from scapy.all import wrpcap, IP, UDP, Raw, Ether

TEMPLATE_ID = 256

IN_BYTES = 1
IN_PKTS = 2
PROTOCOL = 4
IPV4_SRC_ADDR = 8
IPV4_DST_ADDR = 12

def make_nf9_header(count, sequence, source_id=1):
    version = 9
    uptime = 100000
    unix_secs = 1700000000
    # NetFlow v9 header: version(H) count(H) uptime(I) unix_secs(I) sequence(I) source_id(I)
    return struct.pack('!HHIIII', version, count, uptime, unix_secs, sequence, source_id)

def make_template_flowset(template_id=TEMPLATE_ID):
    fields = [
        (IN_BYTES, 4),
        (IN_PKTS, 4),
        (PROTOCOL, 1),
        (IPV4_SRC_ADDR, 4),
        (IPV4_DST_ADDR, 4),
    ]
    field_count = len(fields)
    tmpl = struct.pack('!HH', template_id, field_count)
    for ft, fl in fields:
        tmpl += struct.pack('!HH', ft, fl)
    flowset_body = tmpl
    length = 4 + len(flowset_body)
    if length % 4 != 0:
        pad = 4 - (length % 4)
        flowset_body += b'\x00' * pad
        length += pad
    return struct.pack('!HH', 0, length) + flowset_body

def make_data_flowset(flows, template_id=TEMPLATE_ID):
    # Record layout matches template field order:
    # IN_BYTES(4), IN_PKTS(4), PROTOCOL(1), IPV4_SRC_ADDR(4), IPV4_DST_ADDR(4)
    data = b''
    for f in flows:
        src = socket.inet_aton(f['src_ip'])
        dst = socket.inet_aton(f['dst_ip'])
        proto = f['proto']
        pkts = f['packets']
        byt = f['bytes']
        data += struct.pack('!II', byt, pkts)
        data += struct.pack('!B', proto)
        data += src
        data += dst
    length = 4 + len(data)
    if length % 4 != 0:
        pad = 4 - (length % 4)
        data += b'\x00' * pad
        length += pad
    return struct.pack('!HH', template_id, length) + data

def build_nf9_packet(flowsets, sequence, source_id=1):
    count = len(flowsets)
    header = make_nf9_header(count, sequence, source_id)
    body = b''.join(flowsets)
    return header + body

def make_udp_packet(payload, dst_port=9995):
    pkt = Ether() / IP(src='127.0.0.1', dst='127.0.0.1') / UDP(sport=12345, dport=dst_port) / Raw(load=payload)
    return pkt

def gen_standard(flows, output_path, dst_port=9995):
    pkts = []
    tmpl_fs = make_template_flowset()
    tmpl_pkt = build_nf9_packet([tmpl_fs], sequence=1)
    pkts.append(make_udp_packet(tmpl_pkt, dst_port))
    data_fs = make_data_flowset(flows)
    data_pkt = build_nf9_packet([data_fs], sequence=2)
    pkts.append(make_udp_packet(data_pkt, dst_port))
    wrpcap(output_path, pkts)
    return pkts

def gen_data_before_template(flows, output_path, dst_port=9995):
    pkts = []
    data_fs = make_data_flowset(flows)
    data_pkt = build_nf9_packet([data_fs], sequence=1)
    pkts.append(make_udp_packet(data_pkt, dst_port))
    tmpl_fs = make_template_flowset()
    tmpl_pkt = build_nf9_packet([tmpl_fs], sequence=2)
    pkts.append(make_udp_packet(tmpl_pkt, dst_port))
    wrpcap(output_path, pkts)
    return pkts

def gen_multi_datagram(flow_batches, output_path, dst_port=9995):
    pkts = []
    tmpl_fs = make_template_flowset()
    tmpl_pkt = build_nf9_packet([tmpl_fs], sequence=1)
    pkts.append(make_udp_packet(tmpl_pkt, dst_port))
    for i, batch in enumerate(flow_batches):
        data_fs = make_data_flowset(batch)
        data_pkt = build_nf9_packet([data_fs], sequence=i+2)
        pkts.append(make_udp_packet(data_pkt, dst_port))
    wrpcap(output_path, pkts)
    return pkts

def gen_template_mid_stream(flow_batches_before, flows_after, output_path, dst_port=9995):
    pkts = []
    seq = 1
    for batch in flow_batches_before:
        data_fs = make_data_flowset(batch)
        data_pkt = build_nf9_packet([data_fs], sequence=seq)
        pkts.append(make_udp_packet(data_pkt, dst_port))
        seq += 1
    tmpl_fs = make_template_flowset()
    tmpl_pkt = build_nf9_packet([tmpl_fs], sequence=seq)
    pkts.append(make_udp_packet(tmpl_pkt, dst_port))
    seq += 1
    for batch in flows_after:
        data_fs = make_data_flowset(batch)
        data_pkt = build_nf9_packet([data_fs], sequence=seq)
        pkts.append(make_udp_packet(data_pkt, dst_port))
        seq += 1
    wrpcap(output_path, pkts)
    return pkts

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate NetFlow v9 pcap')
    parser.add_argument('--mode', default='standard',
                        choices=['standard', 'data_first', 'multi_datagram', 'template_mid'])
    parser.add_argument('--flows', type=str, help='JSON array of flow dicts or batches')
    parser.add_argument('--output', required=True, help='Output pcap path')
    parser.add_argument('--port', type=int, default=9995)
    args = parser.parse_args()

    if args.flows:
        flows = json.loads(args.flows)
    else:
        flows = [
            {'src_ip': '192.168.1.1', 'dst_ip': '10.0.0.1', 'proto': 6, 'packets': 100, 'bytes': 150000},
            {'src_ip': '192.168.1.2', 'dst_ip': '10.0.0.2', 'proto': 17, 'packets': 50, 'bytes': 75000},
        ]

    if args.mode == 'standard':
        gen_standard(flows, args.output, args.port)
    elif args.mode == 'data_first':
        gen_data_before_template(flows, args.output, args.port)
    elif args.mode == 'multi_datagram':
        if flows and isinstance(flows[0], list):
            gen_multi_datagram(flows, args.output, args.port)
        else:
            gen_multi_datagram([flows], args.output, args.port)
    elif args.mode == 'template_mid':
        if isinstance(flows, dict):
            gen_template_mid_stream(flows['before'], flows['after'], args.output, args.port)
        else:
            gen_template_mid_stream([], [flows], args.output, args.port)
    print(f'Written to {args.output}')
