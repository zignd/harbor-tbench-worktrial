import sqlite3
import random
import os

os.makedirs('/app/data', exist_ok=True)
db_path = '/app/data/sales.db'

if os.path.exists(db_path):
    os.remove(db_path)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.executescript('''
CREATE TABLE IF NOT EXISTS sales_records (
    record_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    region_id    TEXT NOT NULL,
    sale_amount  REAL NOT NULL,
    sale_date    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS region_summaries (
    region_id      TEXT PRIMARY KEY,
    weighted_total REAL NOT NULL,
    record_count   INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS weight_cache (
    region_id TEXT PRIMARY KEY,
    weight    REAL NOT NULL
);
''')

regions = ['EAST', 'NE', 'NORTH', 'NW', 'SOUTH', 'SE', 'SW', 'WEST']
rng = random.Random(42)

rows = []
for _ in range(2000):
    region = rng.choice(regions)
    amount = round(rng.uniform(10.0, 9999.99), 2)
    year = rng.randint(2022, 2023)
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    date_str = f'{year}-{month:02d}-{day:02d}'
    rows.append((region, amount, date_str))

cur.executemany('INSERT INTO sales_records (region_id, sale_amount, sale_date) VALUES (?, ?, ?)', rows)
conn.commit()

cur.execute('SELECT region_id, COUNT(*) FROM sales_records GROUP BY region_id ORDER BY region_id')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]} records')

conn.close()
print(f'Created {db_path} with 2000 rows')
