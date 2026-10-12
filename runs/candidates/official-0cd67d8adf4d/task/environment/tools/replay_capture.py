#!/usr/bin/env python3
"""Replay a pcap file containing NetFlow v9 UDP datagrams to a local port."""
import sys
import time
import socket
import struct
import argparse


def read_pcap(path):
    """Read a pcap file and yield (timestamp, data) for each packet."""
    with open(path, 'rb') as f:
        # Global header: magic(4) ver_major(2) ver_minor(2) thiszone(4)
        #                sigfigs(4) snaplen(4) network(4)
        hdr = f.read(24)
        if len(hdr) < 24:
            raise ValueError("File too short to be a pcap")
        magic = struct.unpack('<I', hdr[:4])[0]
        if magic == 0xa1b2c3d4:
            endian = '<'
        elif magic == 0xd4c3b2a1:
            endian = '>'
        else:
            raise ValueError(f"Not a pcap file (magic={magic:#010x})")

        while True:
            rec_hdr = f.read(16)
            if len(rec_hdr) < 16:
                break
            ts_sec, ts_usec, incl_len, orig_len = struct.unpack(
                endian + 'IIII', rec_hdr)
            data = f.read(incl_len)
            if len(data) < incl_len:
                break
            yield (ts_sec + ts_usec / 1e6, data)


def extract_udp_payload(frame):
    """Extract UDP payload from an Ethernet/IP/UDP frame.
    Returns None if the frame is not Ethernet+IPv4+UDP.
    """
    # Ethernet header: 14 bytes (dst_mac 6, src_mac 6, ethertype 2)
    if len(frame) < 14:
        return None
    ethertype = struct.unpack('>H', frame[12:14])[0]
    if ethertype != 0x0800:  # IPv4
        return None

    ip_start = 14
    if len(frame) < ip_start + 20:
        return None
    ihl = (frame[ip_start] & 0x0f) * 4
    protocol = frame[ip_start + 9]
    if protocol != 17:  # UDP
        return None

    udp_start = ip_start + ihl
    if len(frame) < udp_start + 8:
        return None
    # UDP header: src_port(2) dst_port(2) length(2) checksum(2)
    udp_length = struct.unpack('>H', frame[udp_start + 4:udp_start + 6])[0]
    payload_start = udp_start + 8
    payload_end = udp_start + udp_length
    if payload_end > len(frame):
        payload_end = len(frame)
    return frame[payload_start:payload_end]


def main():
    parser = argparse.ArgumentParser(
        description='Replay NetFlow v9 UDP datagrams from a pcap file')
    parser.add_argument('pcap', help='Path to the pcap file')
    parser.add_argument('--host', default='127.0.0.1',
                        help='Destination host (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=9995,
                        help='Destination UDP port (default: 9995)')
    parser.add_argument('--delay', type=float, default=0.001,
                        help='Inter-packet delay in seconds (default: 0.001)')
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    count = 0
    errors = 0

    for _ts, frame in read_pcap(args.pcap):
        payload = extract_udp_payload(frame)
        if payload is None:
            continue
        try:
            sock.sendto(payload, (args.host, args.port))
            count += 1
        except OSError as e:
            errors += 1
            print(f"Send error: {e}", file=sys.stderr)
        if args.delay > 0:
            time.sleep(args.delay)

    sock.close()
    print(f"Replayed {count} packets")
    if errors:
        print(f"Errors: {errors}", file=sys.stderr)


if __name__ == '__main__':
    main()
