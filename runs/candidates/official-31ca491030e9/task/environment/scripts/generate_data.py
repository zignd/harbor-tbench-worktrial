#!/usr/bin/env python3
"""Generate events.db and report.sql for the task."""
import sqlite3
import random
import os

RANDOM_SEED = 42
random.seed(RANDOM_SEED)

DB_PATH = "/app/data/events.db"
SQL_PATH = "/app/queries/report.sql"
SAMPLE_PATH = "/app/expected_sample.txt"

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

row_id = 1
all_rows = []

# Standard 20 partitions, zero-padded '01'..'20', 25-35 rows each
for p in range(1, 21):
    pk = f"{p:02d}"
    n_rows = random.randint(25, 35)
    ts_values = sorted(random.sample(range(1000, 9000), n_rows))
    amounts = []
    base_amounts = [round(random.uniform(10.0, 500.0), 2) for _ in range(n_rows)]
    for i in range(n_rows):
        if i > 0 and random.random() < 0.15:
            amounts.append(amounts[random.randint(0, i-1)])
        else:
            amounts.append(base_amounts[i])
    for i in range(n_rows):
        all_rows.append((row_id, pk, ts_values[i], amounts[i]))
        row_id += 1

# Partition '21': contains negative amounts (running_total can decrease)
pk = '21'
ts_neg = [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000]
amt_neg = [100.0, -50.0, 200.0, -30.0, 80.0, -10.0, 300.0, -120.0]
for i in range(len(ts_neg)):
    all_rows.append((row_id, pk, ts_neg[i], amt_neg[i]))
    row_id += 1

# Partition '22': single row
all_rows.append((row_id, '22', 5000, 99.99))
row_id += 1

# Partition '23': all same amount (rank must be 1..n in ts order, no gaps)
pk = '23'
ts_same = sorted(random.sample(range(100, 9900), 10))
for i in range(10):
    all_rows.append((row_id, pk, ts_same[i], 77.77))
    row_id += 1

# Partition '24': exact ties in (amount, ts) - two rows with same amount AND same ts
pk = '24'
# rows: 3 distinct ts values, two rows share ts=2000 and amount=150.0
all_rows.append((row_id, pk, 1000, 200.0))
row_id += 1
all_rows.append((row_id, pk, 2000, 150.0))
row_id += 1
all_rows.append((row_id, pk, 2000, 150.0))
row_id += 1
all_rows.append((row_id, pk, 3000, 100.0))
row_id += 1
# ranks should be: 200.0->1, 150.0/2000->2, 150.0/2000->2 (tie, same rank), 100.0->4 (gap)

# Partition '25': large partition to stress ordering (30 rows, mixed amounts)
pk = '25'
n_large = 30
ts_large = sorted(random.sample(range(500, 9500), n_large))
amt_large = [round(random.uniform(1.0, 1000.0), 2) for _ in range(n_large)]
# insert a few ties
amt_large[5] = amt_large[3]
amt_large[15] = amt_large[10]
amt_large[25] = amt_large[20]
for i in range(n_large):
    all_rows.append((row_id, pk, ts_large[i], amt_large[i]))
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
