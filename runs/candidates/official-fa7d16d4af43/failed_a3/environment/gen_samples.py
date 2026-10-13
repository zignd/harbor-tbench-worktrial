import csv
import random
import os

OUT_PATH = '/app/data/raw_samples.csv'
SEED = 42
NUM_ROWS = 2000
CIRCUITS = ['circuit_A', 'circuit_B', 'circuit_C', 'circuit_D']
HOURS = list(range(24))

rng = random.Random(SEED)
os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)

rows = []
seq = 1
for i in range(NUM_ROWS):
    circuit = rng.choice(CIRCUITS)
    hour = rng.choice(HOURS)
    # Roughly uniform distribution so AVG ~ P90 on sample data
    # (hiding the MIN-as-P90 bug on uniform input)
    raw_count = round(rng.uniform(50.0, 700.0), 2)
    demand_kwh = round(rng.uniform(0.1, 25.0), 4)

    # ~8% leading-zero ids (every 12th row where seq < 1000)
    if i % 12 == 0 and seq < 1000:
        meter_id = f'{seq:04d}'
    else:
        meter_id = str(seq)
    seq += 1

    rows.append({
        'meter_id': meter_id,
        'circuit': circuit,
        'interval_hour': hour,
        'raw_count': raw_count,
        'demand_kwh': demand_kwh,
    })

with open(OUT_PATH, 'w', newline='') as f:
    writer = csv.DictWriter(
        f,
        fieldnames=['meter_id', 'circuit', 'interval_hour', 'raw_count', 'demand_kwh']
    )
    writer.writeheader()
    writer.writerows(rows)

print(f'Generated {len(rows)} rows -> {OUT_PATH}')
