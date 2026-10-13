import sqlite3
import json
import subprocess
import time
import random
import os

DB_PATH = "/app/data/events.db"
LOG_PATH = "/app/data/access.log"
ENRICH_BIN = "/app/bin/enrich"


def init_db():
    conn = sqlite3.connect(DB_PATH)
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
    if not os.path.exists(LOG_PATH):
        conn.close()
        return
    with open(LOG_PATH) as f:
        lines = f.readlines()
    for line in lines[:300]:
        line = line.strip()
        if not line:
            continue
        proc = subprocess.run(
            [ENRICH_BIN],
            input=line + "\n",
            capture_output=True,
            text=True
        )
        out = proc.stdout.strip()
        if not out:
            continue
        try:
            record = json.loads(out)
        except json.JSONDecodeError:
            continue
        country = record.get("country", "UNKNOWN")
        if country == "":
            country = "INTERNAL"
        cur.execute(
            "INSERT OR IGNORE INTO events (ip, method, path, status, country, ts) VALUES (?, ?, ?, ?, ?, ?)",
            (record["ip"], record["method"], record["path"], record["status"], country, time.time() - random.uniform(0, 3600))
        )
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM events")
    count = cur.fetchone()[0]
    print("Initialized DB with", count, "events")
    conn.close()


if __name__ == "__main__":
    init_db()
