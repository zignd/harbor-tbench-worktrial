#!/usr/bin/env python3
"""Generate events.db and report.sql for the task."""
import sqlite3
import random
import os

RANDOM_SEED = 42
random.seed(RANDOM_SEED)

DB_PATH = "/app/data/events.db"
SQL_PATH = "/app/queries/report.sql"

os.makedirs("/app/data", exist_ok=True)
os.makedirs("/app/queries", exist_ok=True)

# Create database
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("DROP TABLE IF EXISTS events")
cur.execute("""
    CREATE TABLE events (
        id INTEGER PRIMARY KEY,
        partition_key TEXT NOT NULL,
        ts INTEGER NOT NULL,
        amount REAL NOT NULL
    )
""")

# Generate 20 partitions, zero-padded '01'..'20'
row_id = 1
all_rows = []
for p in range(1, 21):
    pk = f"{p:02d}"
    n_rows = random.randint(25, 35)
    # Generate unique ts values
    ts_values = sorted(random.sample(range(1000, 9000), n_rows))
    # Generate amounts with some deliberate ties
    amounts = []
    base_amounts = [round(random.uniform(10.0, 500.0), 2) for _ in range(n_rows)]
    # Introduce ties: duplicate some amounts
    for i in range(n_rows):
        if i > 0 and random.random() < 0.15:  # 15% chance of tie
            amounts.append(amounts[random.randint(0, i-1)])
        else:
            amounts.append(base_amounts[i])
    for i in range(n_rows):
        all_rows.append((row_id, pk, ts_values[i], amounts[i]))
        row_id += 1

cur.executemany("INSERT INTO events VALUES (?, ?, ?, ?)", all_rows)
conn.commit()
conn.close()

# Write the broken report.sql
broken_sql = """SELECT partition_key, ts, amount,
       SUM(amount) OVER (PARTITION BY partition_key ORDER BY ts DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total,
       RANK() OVER (PARTITION BY partition_key ORDER BY amount ASC) AS rank
FROM events
ORDER BY partition_key, ts;
"""
with open(SQL_PATH, 'w') as f:
    f.write(broken_sql)

print(f"Generated {DB_PATH} with {row_id-1} rows")
print(f"Generated {SQL_PATH}")
