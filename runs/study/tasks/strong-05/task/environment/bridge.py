import socket
import sqlite3
import struct
import os

DB_PATH = "/var/lib/telemetry/research.db"

def setup_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS telemetry (id INTEGER PRIMARY KEY, ts INTEGER, v1 REAL, v2 REAL, v3 REAL)")
    conn.execute("CREATE TABLE IF NOT EXISTS system_events (id INTEGER, ts INTEGER)")
    conn.commit()
    return conn

def main():
    conn = setup_db()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 9999))

    print("Bridge listening...")
    while True:
        data, addr = sock.recvfrom(1024)
        # Slow naive implementation
        if len(data) == 40:
            try:
                # ID, TS, V1, V2, V3, CRC
                up = struct.unpack("<IQdddI", data)
                conn.execute("INSERT INTO telemetry VALUES (?, ?, ?, ?, ?)", (up[0], up[1], up[2], up[3], up[4]))
                conn.commit() 
            except Exception:
                pass
        # Heartbeats are ignored in this broken version

if __name__ == "__main__":
    main()
