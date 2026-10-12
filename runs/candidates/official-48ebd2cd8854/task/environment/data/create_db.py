#!/usr/bin/env python3
"""
create_db.py  -- generate the initial sales.db for the aggregation service.
Produces ~2000 rows across 8 regions in sales_records, plus empty
region_summaries and weight_cache tables.
"""
import sqlite3
import random
import os

DB_PATH = "/app/data/sales.db"
REGIONS = ["NORTH", "SOUTH", "EAST", "WEST", "NE", "NW", "SE", "SW"]
NUM_ROWS = 2000
SEED = 20240101

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Always start from a clean slate
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.executescript("""
PRAGMA journal_mode=WAL;

CREATE TABLE sales_records (
    record_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    region_id    TEXT    NOT NULL,
    sale_amount  REAL    NOT NULL,
    sale_date    TEXT    NOT NULL
);

CREATE TABLE region_summaries (
    region_id      TEXT PRIMARY KEY,
    weighted_total REAL NOT NULL,
    record_count   INTEGER NOT NULL,
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE weight_cache (
    region_id  TEXT PRIMARY KEY,
    weight     REAL NOT NULL,
    cached_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_sales_region ON sales_records(region_id);
""")

rng = random.Random(SEED)
rows = []
for i in range(NUM_ROWS):
    region = rng.choice(REGIONS)
    amount = round(rng.uniform(10.0, 9999.99), 2)
    date   = "2024-%02d-%02d" % (rng.randint(1,12), rng.randint(1,28))
    rows.append((region, amount, date))

cur.executemany(
    "INSERT INTO sales_records (region_id, sale_amount, sale_date) VALUES (?,?,?)",
    rows
)
conn.commit()

count = cur.execute("SELECT COUNT(*) FROM sales_records").fetchone()[0]
print(f"Inserted {count} rows into sales_records")

conn.close()
print("Done:", DB_PATH)
