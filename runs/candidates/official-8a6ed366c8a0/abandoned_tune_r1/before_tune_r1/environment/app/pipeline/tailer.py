import json
import subprocess
import sqlite3
import time
import os

LOG_PATH = "/app/data/access.log"
DB_PATH = "/app/data/events.db"
ENRICH_BIN = "/app/bin/enrich"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT NOT NULL,
            method TEXT NOT NULL,
            path TEXT NOT NULL,
            status INTEGER NOT NULL,
            country TEXT NOT NULL,
            ts REAL NOT NULL,
            UNIQUE (ip, path, status)
        )
    """)
    conn.commit()
    conn.close()


def process_line(line, conn):
    line = line.strip()
    if not line:
        return
    proc = subprocess.run(
        [ENRICH_BIN],
        input=line + "\n",
        capture_output=True,
        text=True
    )
    out = proc.stdout.strip()
    if not out:
        return
    try:
        import json as _json
        record = _json.loads(out)
    except Exception:
        return
    country = record.get("country", "UNKNOWN")
    if country == "":
        country = "INTERNAL"
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO events (ip, method, path, status, country, ts) VALUES (?, ?, ?, ?, ?, ?)",
        (record["ip"], record["method"], record["path"], record["status"], country, time.time())
    )
    conn.commit()


def tail_log():
    init_db()
    conn = get_db()
    offset = 0
    if os.path.exists(LOG_PATH + ".offset"):
        with open(LOG_PATH + ".offset") as f:
            try:
                offset = int(f.read().strip())
            except Exception:
                offset = 0
    while True:
        try:
            with open(LOG_PATH, "r") as f:
                f.seek(offset)
                lines = f.readlines()
                if lines:
                    for line in lines:
                        process_line(line, conn)
                    offset = f.tell()
                    with open(LOG_PATH + ".offset", "w") as fp:
                        fp.write(str(offset))
        except FileNotFoundError:
            pass
        time.sleep(0.5)


if __name__ == "__main__":
    tail_log()
