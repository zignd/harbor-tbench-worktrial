#!/usr/bin/env python3
"""Generate events.db, report.sql, and expected_sample.txt for the task."""
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

# Compute correct expected output for ALL partitions
def compute_correct(cur, partition_keys=None):
    if partition_keys:
        placeholders = ','.join('?' * len(partition_keys))
        cur.execute(f"SELECT partition_key, ts, amount FROM events WHERE partition_key IN ({placeholders}) ORDER BY partition_key, ts", partition_keys)
    else:
        cur.execute("SELECT partition_key, ts, amount FROM events ORDER BY partition_key, ts")
    rows = cur.fetchall()

    # Group by partition_key
    from collections import defaultdict
    partitions = defaultdict(list)
    for pk, ts, amt in rows:
        partitions[pk].append((ts, amt))

    result_lines = []
    for pk in sorted(partitions.keys()):
        prows = partitions[pk]  # already sorted by ts
        # running total: cumulative sum in ts ASC order
        running = 0.0
        running_totals = []
        for ts, amt in prows:
            running += amt
            running_totals.append(running)

        # rank: rank 1 = highest amount, ties broken by ts ASC (lower ts = lower rank number)
        # meaning: among tied amounts, lower ts gets rank 1 first
        # RANK() with ties: rows with same rank get same rank number, next rank skips
        # But instruction says ties broken by ts ASC -> no actual ties in rank since ts is unique
        # RANK() OVER (PARTITION BY pk ORDER BY amount DESC, ts ASC)
        amounts_ts = [(amt, ts, i) for i, (ts, amt) in enumerate(prows)]
        # Sort by amount DESC, ts ASC to determine rank
        sorted_for_rank = sorted(amounts_ts, key=lambda x: (-x[0], x[1]))
        rank_map = {}  # index -> rank
        cur_rank = 1
        for j, (amt, ts, orig_idx) in enumerate(sorted_for_rank):
            if j == 0:
                rank_map[orig_idx] = cur_rank
            else:
                prev_amt, prev_ts, _ = sorted_for_rank[j-1]
                if amt == prev_amt and ts == prev_ts:  # exact tie (shouldn't happen with unique ts)
                    rank_map[orig_idx] = rank_map[sorted_for_rank[j-1][2]]
                else:
                    cur_rank = j + 1
                    rank_map[orig_idx] = cur_rank

        for i, (ts, amt) in enumerate(prows):
            rt = running_totals[i]
            rk = rank_map[i]
            result_lines.append(f"{pk}\t{ts}\t{amt}\t{rt:.6f}\t{rk}")
    return result_lines

# Generate expected_sample.txt for partitions '10', '15', '20'
sample_lines = compute_correct(cur, ['10', '15', '20'])
with open(SAMPLE_PATH, 'w') as f:
    f.write('\n'.join(sample_lines) + '\n')

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
print(f"Generated {SAMPLE_PATH} with {len(sample_lines)} lines")
