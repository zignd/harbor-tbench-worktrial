#!/usr/bin/env python3
"""Generate synthetic NetFlow v9 pcap files for testing.

Usage examples:
  # 5 flows, template before data (normal order)
  python3 gen_capture.py --out out.pcap \
    --flow 192.168.1.1,10.0.0.1,6,100,50000 \
    --flow 192.168.1.2,10.0.0.2,17,50,20000

  # Data records arrive before template
  python3 gen_capture.py --out out.pcap --data-first \
    --flow 192.168.1.1,10.0.0.1,6,100,50000

  # Multiple datagrams for same flow key (aggregation test)
  python3 gen_capture.py --out out.pcap \
    --flow 192.168.1.1,10.0.0.1,6,10,5000 \
    --flow 192.168.1.1,10.0.0.1,6,20,10000 \
    --split-datagrams
"""
import argparse
import struct
import sys
import ipaddress

# NetFlow v9 field types
FT_IN_BYTES = 1
FT_IN_PKTS = 2
FT_PROTOCOL = 4
FT_IPV4_SRC_ADDR = 8
FT_IPV4_DST_ADDR = 12

# Template ID we'll use
TEMPLATE_ID = 256

# Field layout for our template: src_ip(4), dst_ip(4), proto(1), pkts(4), bytes(4)
FIELD_DEFS = [
    (FT_IPV4_SRC_ADDR, 4),
    (FT_IPV4_DST_ADDR, 4),
    (FT_PROTOCOL, 1),
    (FT_IN_PKTS, 4),
    (FT_IN_BYTES, 4),
]
RECORD_LEN = sum(l for _, l in FIELD_DEFS)  # 17 bytes per record


def build_netflow_header(seq_num, count_flowsets, unix_secs=1700000000):
    """Build a 16-byte NetFlow v9 header."""
    # version(2) count(2) sys_uptime(4) unix_secs(4) seq_number(4) source_id(4)
    return struct.pack(">HHIIII", 9, count_flowsets, 0, unix_secs, seq_num, 1)


def build_template_flowset():
    """Build a template flowset (flowset_id=0)."""
    # Template header: template_id(2) field_count(2)
    tmpl_hdr = struct.pack('>HH', TEMPLATE_ID, len(FIELD_DEFS))
    # Field definitions: type(2) length(2) each
    fields = b''.join(struct.pack('>HH', ft, fl) for ft, fl in FIELD_DEFS)
    tmpl_data = tmpl_hdr + fields
    # Flowset header: flowset_id(2) length(2) — length includes the 4-byte header
    fs_len = 4 + len(tmpl_data)
    # Pad to 4-byte boundary
    pad = (4 - fs_len % 4) % 4
    return struct.pack('>HH', 0, fs_len + pad) + tmpl_data + (b'\x00' * pad)


def build_data_record(src_ip_int, dst_ip_int, proto, packets, nbytes):
    """Build a single 17-byte data record."""
    return struct.pack('>IIBII',
        src_ip_int, dst_ip_int, proto,
        packets & 0xffffffff, nbytes & 0xffffffff)


def build_data_flowset(records):
    """Build a data flowset containing the given records."""
    data = b''.join(records)
    fs_len = 4 + len(data)
    pad = (4 - fs_len % 4) % 4
    return struct.pack('>HH', TEMPLATE_ID, fs_len + pad) + data + (b'\x00' * pad)


def build_netflow_datagram(flowsets, seq_num):
    """Wrap flowsets in a NetFlow v9 datagram."""
    hdr = build_netflow_header(seq_num, len(flowsets))
    return hdr + b''.join(flowsets)


def wrap_udp_packet(payload, src_ip='10.0.0.100', dst_ip='127.0.0.1',
                    src_port=12345, dst_port=9995):
    """Wrap a UDP payload in Ethernet+IPv4+UDP frame."""
    src_ip_b = ipaddress.IPv4Address(src_ip).packed
    dst_ip_b = ipaddress.IPv4Address(dst_ip).packed

    # UDP header
    udp_len = 8 + len(payload)
    udp_hdr = struct.pack('>HHHH', src_port, dst_port, udp_len, 0)

    # IPv4 header (no options, TTL=64)
    ip_len = 20 + udp_len
    ip_hdr = struct.pack('>BBHHHBBH4s4s',
        0x45, 0,          # version+ihl, dscp+ecn
        ip_len,           # total length
        0, 0,             # identification, flags+fragment offset
        64, 17,           # TTL, protocol (UDP)
        0,                # checksum (0 = unchecked)
        src_ip_b, dst_ip_b)

    # Ethernet header (fake MACs)
    eth_hdr = b'\x00\x00\x00\x00\x00\x01' \
              b'\x00\x00\x00\x00\x00\x02' \
              + struct.pack('>H', 0x0800)

    return eth_hdr + ip_hdr + udp_hdr + payload


def write_pcap(path, frames):
    """Write frames to a pcap file."""
    # pcap global header
    pcap_hdr = struct.pack('<IHHiIII',
        0xa1b2c3d4,  # magic
        2, 4,        # major, minor version
        0,           # thiszone
        0,           # sigfigs
        65535,       # snaplen
        1,           # network (Ethernet)
    )
    with open(path, 'wb') as f:
        f.write(pcap_hdr)
        ts = 1700000000.0
        for frame in frames:
            ts += 0.001
            ts_sec = int(ts)
            ts_usec = int((ts - ts_sec) * 1e6)
            f.write(struct.pack('<IIII',
                ts_sec, ts_usec, len(frame), len(frame)))
            f.write(frame)


def parse_flow_spec(spec):
    """Parse 'src_ip,dst_ip,proto,packets,bytes' into a tuple."""
    parts = spec.split(',')
    if len(parts) != 5:
        raise ValueError(f"Flow spec must be src_ip,dst_ip,proto,packets,bytes: {spec!r}")
    src_ip = int(ipaddress.IPv4Address(parts[0]))
    dst_ip = int(ipaddress.IPv4Address(parts[1]))
    proto = int(parts[2])
    packets = int(parts[3])
    nbytes = int(parts[4])
    return (src_ip, dst_ip, proto, packets, nbytes)


def main():
    parser = argparse.ArgumentParser(description='Generate NetFlow v9 pcap files')
    parser.add_argument('--out', required=True, help='Output pcap file path')
    parser.add_argument('--flow', action='append', dest='flows', default=[],
                        metavar='SRC,DST,PROTO,PKTS,BYTES',
                        help='Add a flow (may be repeated)')
    parser.add_argument('--data-first', action='store_true',
                        help='Send data records before template (out-of-order)')
    parser.add_argument('--split-datagrams', action='store_true',
                        help='Put each flow in its own datagram (with template in first)')
    parser.add_argument('--template-datagram', type=int, default=1,
                        metavar='N',
                        help='Which datagram (1-based) carries the template '
                             '(default: 1; use with --split-datagrams)')
    args = parser.parse_args()

    if not args.flows:
        print('No flows specified. Use --flow SRC,DST,PROTO,PKTS,BYTES', file=sys.stderr)
        sys.exit(1)

    flows = [parse_flow_spec(f) for f in args.flows]

    frames = []
    seq = 1

    if args.split_datagrams:
        # Each flow gets its own datagram; template goes in datagram N
        # (default 1 = first datagram)
        tmpl_datagram_idx = args.template_datagram - 1  # 0-based
        for i, (src_ip, dst_ip, proto, pkts, nbytes) in enumerate(flows):
            rec = build_data_record(src_ip, dst_ip, proto, pkts, nbytes)
            data_fs = build_data_flowset([rec])
            if i == tmpl_datagram_idx:
                tmpl_fs = build_template_flowset()
                dgram = build_netflow_datagram([tmpl_fs, data_fs], seq)
            else:
                dgram = build_netflow_datagram([data_fs], seq)
            seq += 1
            frames.append(wrap_udp_packet(dgram))
        # If template_datagram_idx is beyond flow count, add a standalone template
        if tmpl_datagram_idx >= len(flows):
            tmpl_fs = build_template_flowset()
            dgram = build_netflow_datagram([tmpl_fs], seq)
            seq += 1
            frames.append(wrap_udp_packet(dgram))
    elif args.data_first:
        # Data records datagram comes first, template datagram second
        records = [build_data_record(*f) for f in flows]
        data_fs = build_data_flowset(records)
        data_dgram = build_netflow_datagram([data_fs], seq)
        seq += 1
        frames.append(wrap_udp_packet(data_dgram))

        tmpl_fs = build_template_flowset()
        tmpl_dgram = build_netflow_datagram([tmpl_fs], seq)
        seq += 1
        frames.append(wrap_udp_packet(tmpl_dgram))

        # A second data datagram so records are processed after template
        data_dgram2 = build_netflow_datagram([data_fs], seq)
        seq += 1
        frames.append(wrap_udp_packet(data_dgram2))
    else:
        # Normal: template first, then all data records in one datagram
        tmpl_fs = build_template_flowset()
        tmpl_dgram = build_netflow_datagram([tmpl_fs], seq)
        seq += 1
        frames.append(wrap_udp_packet(tmpl_dgram))

        records = [build_data_record(*f) for f in flows]
        data_fs = build_data_flowset(records)
        data_dgram = build_netflow_datagram([data_fs], seq)
        seq += 1
        frames.append(wrap_udp_packet(data_dgram))

    write_pcap(args.out, frames)
    print(f"Wrote {len(frames)} packets to {args.out}")


if __name__ == '__main__':
    main()
