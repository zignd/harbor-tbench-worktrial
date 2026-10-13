#!/usr/bin/env python3
"""Replay a pcap file's UDP packets to localhost:9995."""
import sys
import time
import socket
from scapy.all import rdpcap, UDP

def replay(pcap_path, dst_host='127.0.0.1', dst_port=9995, delay=0.001):
    pkts = rdpcap(pcap_path)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    count = 0
    for pkt in pkts:
        if UDP in pkt:
            payload = bytes(pkt[UDP].payload)
            if payload:
                sock.sendto(payload, (dst_host, dst_port))
                count += 1
                time.sleep(delay)
    sock.close()
    print(f'Replayed {count} packets')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: replay_capture.py <pcap_file> [host] [port]')
        sys.exit(1)
    pcap = sys.argv[1]
    host = sys.argv[2] if len(sys.argv) > 2 else '127.0.0.1'
    port = int(sys.argv[3]) if len(sys.argv) > 3 else 9995
    replay(pcap, host, port)
