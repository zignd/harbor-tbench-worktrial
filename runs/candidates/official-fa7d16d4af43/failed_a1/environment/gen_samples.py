#!/usr/bin/env python3
"""Generate the initial raw_samples.csv for the pipeline environment.

The sample dataset uses a near-uniform raw_value distribution so that
AVG approximates P90, keeping the SQL bug invisible on sample data.
About 8 percent of reading_ids carry leading zeros.
"""
import csv
import os
import random

RANDOM_SEED = 20240101
OUTPUT_PATH = '/app/data/raw_samples.csv'
NUM_ROWS = 2000
ZONES = ['zone_alpha', 'zone_beta', 'zone_gamma', 'zone_delta', 'zone_epsilon']
HOURS = list(range(24))


def main():
    rng = random.Random(RANDOM_SEED)
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    rows = []
    seq = 1
    for i in range(NUM_ROWS):
        zone = rng.choice(ZONES)
        hour = rng.choice(HOURS)
        # Near-uniform raw_value in 100-900 range so AVG ~ P90
        raw_value = round(rng.uniform(100.0, 900.0), 2)
        raw_energy_wh = round(rng.uniform(0.5, 25.0), 4)

        # About 8% of IDs get leading-zero formatting
        if i % 12 == 0 and seq < 1000:
            reading_id = f'{seq:04d}'  # e.g. '0001', '0002'
        else:
            reading_id = str(seq)
        seq += 1

        rows.append({
            'reading_id': reading_id,
            'zone': zone,
            'timestamp_hour': hour,
            'raw_value': raw_value,
            'raw_energy_wh': raw_energy_wh,
        })

    with open(OUTPUT_PATH, 'w', newline='') as f:
        writer = csv.DictWriter(
            f,
            fieldnames=['reading_id', 'zone', 'timestamp_hour',
                        'raw_value', 'raw_energy_wh']
        )
        writer.writeheader()
        writer.writerows(rows)

    leading_zero_count = sum(
        1 for r in rows if r['reading_id'] != str(int(r['reading_id']))
    )
    print(f'Wrote {len(rows)} rows to {OUTPUT_PATH}')
    print(f'Leading-zero IDs: {leading_zero_count} ({leading_zero_count/len(rows)*100:.1f}%)')


if __name__ == '__main__':
    main()
