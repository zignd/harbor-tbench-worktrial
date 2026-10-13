import sqlite3
import subprocess
import random

def get_fee(d, i):
    res = subprocess.check_output(['/usr/bin/calculate_fee', str(d), str(i)])
    return float(res.strip())

conn = sqlite3.connect('usage.db')
c = conn.cursor()
c.execute('CREATE TABLE charges (id INTEGER PRIMARY KEY, duration REAL, intensity REAL, amount REAL)')

random.seed(42)
for i in range(500):
    d = random.uniform(0.1, 200.0)
    inst = random.uniform(0.1, 1.2)
    true_amount = get_fee(d, inst)
    if random.random() < 0.15:
        amount = true_amount + random.uniform(0.01, 1.0) * (1 if random.random() > 0.5 else -1)
    else:
        amount = true_amount
    c.execute('INSERT INTO charges (duration, intensity, amount) VALUES (?, ?, ?)', (d, inst, amount))

conn.commit()
conn.close()
