import socket
import struct
import time
import os

CORPUS_FILE = os.path.join(os.path.dirname(__file__), 'corpus.bin')

def load_corpus():
    with open(CORPUS_FILE, 'rb') as f:
        data = f.read()
    records = []
    pos = 0
    while pos + 4 <= len(data):
        length = struct.unpack_from('<I', data, pos)[0]
        pos += 4
        if pos + length > len(data):
            break
        records.append(data[pos:pos+length])
        pos += length
    return records

def handle_client(conn, records):
    try:
        for i, record in enumerate(records):
            # Every 3rd record (starting at index 1) gets fragmented into two sends
            if i % 3 == 1 and len(record) > 10:
                split = len(record) // 2
                # Send length prefix first, then data in two chunks
                conn.sendall(struct.pack('<I', len(record)))
                conn.sendall(record[:split])
                time.sleep(0.01)
                conn.sendall(record[split:])
            else:
                conn.sendall(struct.pack('<I', len(record)))
                conn.sendall(record)
    except Exception:
        pass
    finally:
        conn.close()

def main():
    records = load_corpus()
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('0.0.0.0', 7823))
    srv.listen(16)
    while True:
        conn, _ = srv.accept()
        handle_client(conn, records)

if __name__ == '__main__':
    main()
