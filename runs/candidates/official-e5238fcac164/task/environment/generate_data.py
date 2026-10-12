#!/usr/bin/env python3
"""
generate_data.py - Creates synthetic NetFlow v9 binary data files and
the ASN mapping table used by the settlement service.

Run this script once during Docker image build to populate /app/data/.
"""

import csv
import os
import random
import socket
import struct
import sys

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# ASN map - 40 CIDR prefixes, 8 ASN counterparties
# ---------------------------------------------------------------------------

CIDRS = [
    ('10.0.0.0/8',       'AS64512'),
    ('10.1.0.0/16',      'AS64512'),
    ('10.2.0.0/16',      'AS64512'),
    ('10.3.0.0/24',      'AS64512'),
    ('10.4.0.0/24',      'AS64512'),
    ('172.16.0.0/12',    'AS64513'),
    ('172.17.0.0/16',    'AS64513'),
    ('172.18.0.0/16',    'AS64513'),
    ('172.19.0.0/24',    'AS64513'),
    ('172.20.0.0/24',    'AS64513'),
    ('192.168.0.0/16',   'AS64514'),
    ('192.168.1.0/24',   'AS64514'),
    ('192.168.2.0/24',   'AS64514'),
    ('192.168.3.0/24',   'AS64514'),
    ('192.168.4.0/24',   'AS64514'),
    ('198.51.100.0/24',  'AS64515'),
    ('198.51.101.0/24',  'AS64515'),
    ('198.51.102.0/24',  'AS64515'),
    ('198.51.103.0/24',  'AS64515'),
    ('198.51.104.0/24',  'AS64515'),
    ('203.0.113.0/24',   'AS64516'),
    ('203.0.114.0/24',   'AS64516'),
    ('203.0.115.0/24',   'AS64516'),
    ('203.0.116.0/24',   'AS64516'),
    ('203.0.117.0/24',   'AS64516'),
    ('100.64.0.0/10',    'AS64517'),
    ('100.65.0.0/16',    'AS64517'),
    ('100.66.0.0/16',    'AS64517'),
    ('100.67.0.0/24',    'AS64517'),
    ('100.68.0.0/24',    'AS64517'),
    ('169.254.0.0/16',   'AS64518'),
    ('169.254.1.0/24',   'AS64518'),
    ('169.254.2.0/24',   'AS64518'),
    ('169.254.3.0/24',   'AS64518'),
    ('169.254.4.0/24',   'AS64518'),
    ('192.0.2.0/24',     'AS64519'),
    ('192.0.3.0/24',     'AS64519'),
    ('192.0.4.0/24',     'AS64519'),
    ('192.0.5.0/24',     'AS64519'),
    ('192.0.6.0/24',     'AS64519'),
]

# One representative IP per ASN (falls within a listed CIDR)
ASN_IPS = {
    'AS64512': '10.1.5.5',
    'AS64513': '172.17.1.1',
    'AS64514': '192.168.1.50',
    'AS64515': '198.51.100.99',
    'AS64516': '203.0.113.42',
    'AS64517': '100.65.20.30',
    'AS64518': '169.254.1.200',
    'AS64519': '192.0.2.7',
}

# ---------------------------------------------------------------------------
# Template definitions
# TID = 300 used for all sample data files
# Template A: SRC DST BYTES PKTS PROTO SPORT DPORT (standard order)
# Template B: SRC BYTES PROTO DST PKTS SPORT DPORT (revised field order)
# Both have the same template ID so Template B is a re-export of Template A.
# ---------------------------------------------------------------------------

TID = 300
# Field type IDs (RFC 3954)
F_SRC   = 8    # IPV4_SRC_ADDR
F_DST   = 12   # IPV4_DST_ADDR
F_BYTES = 1    # IN_BYTES
F_PKTS  = 2    # IN_PKTS
F_PROTO = 4    # PROTOCOL
F_SPORT = 7    # L4_SRC_PORT
F_DPORT = 11   # L4_DST_PORT

# Template A field list: (type_id, length)
FA = [
    (F_SRC,   4),
    (F_DST,   4),
    (F_BYTES, 4),
    (F_PKTS,  4),
    (F_PROTO, 1),
    (F_SPORT, 2),
    (F_DPORT, 2),
]
# Template B field list: different layout for same TID
FB = [
    (F_SRC,   4),
    (F_BYTES, 4),
    (F_PROTO, 1),
    (F_DST,   4),
    (F_PKTS,  4),
    (F_SPORT, 2),
    (F_DPORT, 2),
]

RECORD_LEN_A = sum(l for _, l in FA)  # 21
RECORD_LEN_B = sum(l for _, l in FB)  # 21

# ---------------------------------------------------------------------------
# Binary encoding helpers
# ---------------------------------------------------------------------------

def ip4(s):
    return socket.inet_aton(s)

def u8(v):
    return struct.pack('!B', v & 0xFF)

def u16(v):
    return struct.pack('!H', v & 0xFFFF)

def u32(v):
    return struct.pack('!I', v & 0xFFFFFFFF)

def pad4(b):
    """Pad bytes to the next 4-byte boundary."""
    r = len(b) % 4
    if r:
        b += b'\x00' * (4 - r)
    return b

def nf9_header(flowset_count, seq_num, uptime=60000, unix_secs=1700000000, source_id=1):
    """Build a 20-byte NetFlow v9 packet header."""
    return struct.pack('!HHIIII', 9, flowset_count, uptime, unix_secs, seq_num, source_id)

def template_flowset(tid, fields):
    """Build a Template FlowSet containing one template."""
    body = struct.pack('!HH', tid, len(fields))
    for ftype, flen in fields:
        body += struct.pack('!HH', ftype, flen)
    body = pad4(body)
    return struct.pack('!HH', 0, 4 + len(body)) + body

def data_flowset(tid, records_bytes):
    """Build a Data FlowSet from pre-encoded record bytes."""
    body = pad4(records_bytes)
    return struct.pack('!HH', tid, 4 + len(body)) + body

def encode_record(src_ip, in_bytes, dst_ip, pkts, proto, sport, dport, fields):
    """Encode a flow record according to the given field list."""
    vals = {
        F_SRC:   ip4(src_ip),
        F_DST:   ip4(dst_ip),
        F_BYTES: u32(in_bytes),
        F_PKTS:  u32(pkts),
        F_PROTO: u8(proto),
        F_SPORT: u16(sport),
        F_DPORT: u16(dport),
    }
    return b''.join(vals[ft] for ft, fl in fields)

# ---------------------------------------------------------------------------
# Generate flow records
# ---------------------------------------------------------------------------

rng = random.Random(0xABCD1234)

def random_flow(src_ip, fields):
    """Return (record_bytes, in_bytes) for a random flow from src_ip."""
    in_bytes = rng.randint(1000, 999999)
    pkts     = rng.randint(1, in_bytes // 64 + 1)
    proto    = rng.choice([6, 17, 1])
    sport    = rng.randint(1024, 65535)
    dport    = rng.choice([80, 443, 53, 22, 8080])
    dst_ip   = '8.8.8.8'
    rec      = encode_record(src_ip, in_bytes, dst_ip, pkts, proto, sport, dport, fields)
    return rec, in_bytes

# Map to track expected totals for reference CSV
expected: dict = {asn: 0 for asn in ASN_IPS}

def flows_for_asns(asn_list, fields, n_each=3):
    """Generate n_each flow records per ASN in asn_list."""
    rec_bytes = b''
    for asn in asn_list:
        src_ip = ASN_IPS[asn]
        for _ in range(n_each):
            rec, ib = random_flow(src_ip, fields)
            rec_bytes += rec
            expected[asn] += ib
    return rec_bytes

# ---------------------------------------------------------------------------
# Build the 6 sample binary files
# ---------------------------------------------------------------------------

# flows_001.bin: Template A + data records for 4 ASNs
asns_1 = ['AS64512', 'AS64513', 'AS64514', 'AS64515']
recs_1 = flows_for_asns(asns_1, FA, n_each=4)
pkt_1 = (nf9_header(2, seq_num=1) +
         template_flowset(TID, FA) +
         data_flowset(TID, recs_1))
with open(os.path.join(OUT_DIR, 'flows_001.bin'), 'wb') as f:
    f.write(pkt_1)
print('Wrote flows_001.bin')

# flows_002.bin: Template A + data records for remaining 4 ASNs
asns_2 = ['AS64516', 'AS64517', 'AS64518', 'AS64519']
recs_2 = flows_for_asns(asns_2, FA, n_each=4)
pkt_2 = (nf9_header(2, seq_num=2) +
         template_flowset(TID, FA) +
         data_flowset(TID, recs_2))
with open(os.path.join(OUT_DIR, 'flows_002.bin'), 'wb') as f:
    f.write(pkt_2)
print('Wrote flows_002.bin')

# flows_003.bin: Two NetFlow packets concatenated
#   Packet 1: Template A + data records encoded with Template A
#   Packet 2: Template B (same TID, different field order) + data records encoded with Template B
# This file tests mid-file template revision.
asns_3a = ['AS64512', 'AS64516']
recs_3a = flows_for_asns(asns_3a, FA, n_each=3)
pkt_3a = (nf9_header(2, seq_num=3) +
          template_flowset(TID, FA) +
          data_flowset(TID, recs_3a))

asns_3b = ['AS64513', 'AS64517']
recs_3b = flows_for_asns(asns_3b, FB, n_each=3)
pkt_3b = (nf9_header(2, seq_num=4) +
          template_flowset(TID, FB) +
          data_flowset(TID, recs_3b))

with open(os.path.join(OUT_DIR, 'flows_003.bin'), 'wb') as f:
    f.write(pkt_3a + pkt_3b)
print('Wrote flows_003.bin')

# flows_004.bin: Data-only, uses Template B layout (no template export)
# Requires cross-file template state from flows_003.bin
asns_4 = ['AS64514', 'AS64518']
recs_4 = flows_for_asns(asns_4, FB, n_each=4)
pkt_4 = nf9_header(1, seq_num=5) + data_flowset(TID, recs_4)
with open(os.path.join(OUT_DIR, 'flows_004.bin'), 'wb') as f:
    f.write(pkt_4)
print('Wrote flows_004.bin')

# flows_005.bin: Data-only, uses Template B layout
asns_5 = ['AS64515', 'AS64519']
recs_5 = flows_for_asns(asns_5, FB, n_each=4)
pkt_5 = nf9_header(1, seq_num=6) + data_flowset(TID, recs_5)
with open(os.path.join(OUT_DIR, 'flows_005.bin'), 'wb') as f:
    f.write(pkt_5)
print('Wrote flows_005.bin')

# flows_006.bin: Data-only, uses Template B layout
asns_6 = ['AS64512', 'AS64519']
recs_6 = flows_for_asns(asns_6, FB, n_each=3)
pkt_6 = nf9_header(1, seq_num=7) + data_flowset(TID, recs_6)
with open(os.path.join(OUT_DIR, 'flows_006.bin'), 'wb') as f:
    f.write(pkt_6)
print('Wrote flows_006.bin')

# ---------------------------------------------------------------------------
# Write asn_map.csv
# ---------------------------------------------------------------------------

with open(os.path.join(OUT_DIR, 'asn_map.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['cidr', 'asn'])
    for cidr, asn in CIDRS:
        w.writerow([cidr, asn])
print('Wrote asn_map.csv')

# ---------------------------------------------------------------------------
# Write reference_totals.csv
# (Ground truth for the sample data files - not used by tests directly)
# ---------------------------------------------------------------------------

with open(os.path.join(OUT_DIR, 'reference_totals.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['asn', 'bytes'])
    for asn in sorted(expected):
        w.writerow([asn, expected[asn]])
print('Wrote reference_totals.csv')
print('Expected totals:', {k: v for k, v in expected.items() if v > 0})
