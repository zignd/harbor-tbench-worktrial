import socket
import redis
import sqlite3
import struct
import os

DB_PATH = "/var/lib/telemetry/research.db"
REDIS_HOST = "localhost"

def setup_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS telemetry (id INTEGER PRIMARY KEY, ts INTEGER, v1 REAL, v2 REAL, v3 REAL)")
    conn.execute("CREATE TABLE IF NOT EXISTS system_events (id INTEGER, ts INTEGER)")
    conn.commit()
    return conn

def main():
    conn = setup_db()
    r = redis.Redis(host=REDIS_HOST)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 9999))
    
    print("Bridge listening...")
    while True:
        data, addr = sock.recvfrom(1024)
        # NAIVE IMPLEMENTATION: 
        # 1. Doesn't check length, assumes 40 bytes
        # 2. Synchronous SQLite write per packet
        # 3. No Redis buffering (reads directly from socket)
        try:
            if len(data) == 40:
                unpacked = struct.unpack("<IQdddI", data)
                conn.execute("INSERT INTO telemetry VALUES (?, ?, ?, ?, ?)", 
                             (unpacked[0], unpacked[1], unpacked[2], unpacked[3], unpacked[4]))
                conn.commit()
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
