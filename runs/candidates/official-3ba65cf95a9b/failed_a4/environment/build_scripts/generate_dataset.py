import os, struct, random, sqlite3, json

SHARD_MAGIC = 0x44524853
HEADER_FMT = '<IIII'
RECORD_FMT = '<Q16s64s24s16sQIQ340s'

Q1_SQL = '''
WITH commit_results AS (
    SELECT
        test_name,
        commit_hash,
        MAX(CASE WHEN outcome = 'PASSED' THEN 1 ELSE 0 END) AS has_pass,
        MAX(CASE WHEN outcome IN ('FAILED', 'TIMEOUT') THEN 1 ELSE 0 END) AS has_fail
    FROM test_events
    WHERE timestamp BETWEEN 1710604800000 AND 1711209600000
    GROUP BY test_name, commit_hash
)
SELECT
    test_name,
    COUNT(*) AS total_commits,
    SUM(CASE WHEN has_pass = 1 AND has_fail = 1 THEN 1 ELSE 0 END) AS flaky_commits,
    ROUND(CAST(SUM(CASE WHEN has_pass = 1 AND has_fail = 1 THEN 1 ELSE 0 END) AS REAL) / COUNT(*), 4) AS flake_rate
FROM commit_results
GROUP BY test_name
HAVING flaky_commits > 0
ORDER BY flake_rate DESC, flaky_commits DESC, test_name ASC
LIMIT 25;
'''

Q2_SQL = '''
WITH ranked_durations AS (
    SELECT
        runner_pool,
        duration_us,
        ROW_NUMBER() OVER (PARTITION BY runner_pool ORDER BY duration_us ASC) AS rnk,
        COUNT(*) OVER (PARTITION BY runner_pool) AS pool_total
    FROM test_events
    WHERE timestamp BETWEEN 1710604800000 AND 1711209600000
)
SELECT
    runner_pool,
    pool_total AS sample_count,
    duration_us AS p95_duration_us
FROM ranked_durations
WHERE rnk = CAST(0.95 * pool_total AS INT)
ORDER BY runner_pool ASC;
'''

Q3_SQL = '''
SELECT
    test_name,
    commit_hash,
    COUNT(*) AS execution_count,
    ROUND(AVG(duration_us), 2) AS avg_duration_us,
    MAX(duration_us) AS max_duration_us
FROM test_events
WHERE timestamp BETWEEN 1710604800000 AND 1711209600000
GROUP BY test_name, commit_hash
HAVING execution_count >= 5
ORDER BY avg_duration_us DESC, test_name ASC
LIMIT 30;
'''

Q4_SQL = '''
SELECT
    runner_pool,
    COUNT(*) AS total_runs,
    SUM(CASE WHEN outcome IN ('FAILED', 'TIMEOUT') THEN 1 ELSE 0 END) AS failed_runs,
    ROUND(CAST(SUM(CASE WHEN outcome IN ('FAILED', 'TIMEOUT') THEN 1 ELSE 0 END) AS REAL) / COUNT(*), 4) AS failure_rate,
    ROUND(AVG(duration_us), 2) AS mean_duration_us
FROM test_events
WHERE timestamp BETWEEN 1710604800000 AND 1711209600000
GROUP BY runner_pool
ORDER BY failure_rate DESC, runner_pool ASC;
'''

def generate_records(seed, num_shards, records_per_shard, is_sample=False):
    random.seed(seed)
    commits = [f'c{i:02d}a1b2c3d4e5' for i in range(25)]
    tests = [f'test_{mod}_{i:02d}' for mod in ['auth', 'db', 'worker', 'api'] for i in range(20)]
    pools = ['linux-x86_64', 'linux-arm64', 'windows-2022', 'macos-13']
    pool_base = {'linux-x86_64': 1000000, 'linux-arm64': 800000, 'windows-2022': 2800000, 'macos-13': 2200000}
    all_shards = []
    rec_counter = 1
    for s_idx in range(num_shards):
        shard_records = []
        for _ in range(records_per_shard):
            rec_id = rec_counter
            rec_counter += 1
            commit = random.choice(commits)
            test = random.choice(tests)
            pool = random.choice(pools)
            if is_sample:
                flag = 0x00
                r_out = random.random()
                outcome = 'PASSED' if r_out < 0.80 else ('FAILED' if r_out < 0.95 else 'SKIPPED')
                duration = int(pool_base[pool] * random.uniform(0.3, 1.6))
                ts_ms = 1710604800000 + random.randint(0, 604799000)
                ts_file = ts_ms
            else:
                r_flag = random.random()
                if r_flag < 0.05: flag = 0x01
                elif r_flag < 0.11: flag = 0x02
                elif r_flag < 0.15: flag = 0x06
                else: flag = 0x00
                if flag & 0x01:
                    outcome = random.choice(['FAILED', 'TIMEOUT'])
                    duration = random.randint(10000, 300000)
                else:
                    r_out = random.random()
                    outcome = 'PASSED' if r_out < 0.78 else ('FAILED' if r_out < 0.90 else ('TIMEOUT' if r_out < 0.95 else 'SKIPPED'))
                    duration = int(pool_base[pool] * random.uniform(0.1, 1.8))
                ts_ms = 1710604800000 + random.randint(0, 604799000) if random.random() < 0.85 else 1710000000000 + random.randint(0, 604799000)
                ts_file = ts_ms * 1000 + random.randint(0, 999) if s_idx >= (num_shards // 2) else ts_ms
            shard_records.append((rec_id, commit, test, pool, outcome, duration, flag, ts_file, ts_ms))
        all_shards.append(shard_records)
    return all_shards

def write_shard_file(filepath, version, records):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'wb') as fp:
        fp.write(struct.pack(HEADER_FMT, SHARD_MAGIC, version, len(records), 0))
        for r in records:
            rec_id, commit, test, pool, outcome, duration, flag, ts_file, _ = r
            fp.write(struct.pack(RECORD_FMT, rec_id, commit.encode('ascii'), test.encode('ascii'), pool.encode('ascii'), outcome.encode('ascii'), duration, flag, ts_file, b'\x00'*340))

def compute_reference_metrics(shards_records):
    conn = sqlite3.connect(':memory:')
    conn.execute('''CREATE TABLE test_events (record_id INTEGER PRIMARY KEY, commit_hash TEXT, test_name TEXT, runner_pool TEXT, outcome TEXT, duration_us INTEGER, flags INTEGER, timestamp INTEGER)''')
    valid_rows = []
    for shard in shards_records:
        for r in shard:
            rec_id, commit, test, pool, outcome, duration, flag, ts_file, ts_ms = r
            if (flag & 0x05) == 0 and outcome != 'SKIPPED':
                valid_rows.append((rec_id, commit, test, pool, outcome, duration, flag, ts_ms))
    conn.executemany('INSERT INTO test_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)', valid_rows)
    conn.commit()
    return {'q1': conn.execute(Q1_SQL).fetchall(), 'q2': conn.execute(Q2_SQL).fetchall(), 'q3': conn.execute(Q3_SQL).fetchall(), 'q4': conn.execute(Q4_SQL).fetchall()}

def main():
    shards_dir = '/var/lib/build_data/shards'
    ref_file = '/var/lib/build_data/reference_metrics.json'
    sample_dir = '/repo/sample_data'
    prod_shards = generate_records(seed=42, num_shards=32, records_per_shard=5625, is_sample=False)
    for i, records in enumerate(prod_shards):
        write_shard_file(os.path.join(shards_dir, f'shard_{i:02d}.dat'), 2 if i >= 16 else 1, records)
    ref_metrics = compute_reference_metrics(prod_shards)
    os.makedirs(os.path.dirname(ref_file), exist_ok=True)
    with open(ref_file, 'w') as f: json.dump(ref_metrics, f, indent=2)
    sample_shards = generate_records(seed=123, num_shards=1, records_per_shard=2000, is_sample=True)
    write_shard_file(os.path.join(sample_dir, 'sample_01.dat'), 1, sample_shards[0])
    with open(os.path.join(sample_dir, 'sample_reference.json'), 'w') as f:
        json.dump(compute_reference_metrics(sample_shards), f, indent=2)

if __name__ == '__main__':
    main()
