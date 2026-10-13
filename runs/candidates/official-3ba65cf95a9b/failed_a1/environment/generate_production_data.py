import os
import sys
import struct
import random
import sqlite3
import json

def create_generator(seed=42):
    random.seed(seed)
    pools = ["pool-c5-large", "pool-m5-xlarge", "pool-r5-2xlarge", "pool-t3-medium"]
    pool_dur_mult = {
        "pool-c5-large": 0.85,
        "pool-m5-xlarge": 1.00,
        "pool-r5-2xlarge": 0.70,
        "pool-t3-medium": 1.45,
    }
    categories = ["auth", "billing", "catalog", "checkout", "search"]
    test_names = [f"test_{cat}_{i:02d}" for cat in categories for i in range(1, 9)]
    commits = [f"c{i:04x}abcdef12" for i in range(50)]
    
    flaky_tests = set(["test_auth_03", "test_billing_02", "test_catalog_07", "test_checkout_05", "test_search_01", "test_billing_06", "test_catalog_02"])
    broken_commits = {("test_auth_08", "c0005abcdef12"), ("test_search_04", "c0012abcdef12"), ("test_checkout_02", "c0022abcdef12")}
    regression_commits = {
        ("test_billing_05", "c0010abcdef12"): 920000,
        ("test_checkout_01", "c0003abcdef12"): 850000,
        ("test_catalog_04", "c0018abcdef12"): 780000,
        ("test_auth_01", "c0025abcdef12"): 650000
    }
    
    return pools, pool_dur_mult, test_names, commits, flaky_tests, broken_commits, regression_commits

def write_shard(path, records):
    with open(path, "wb") as f:
        f.write(b"TLMSHRD1")
        f.write(struct.pack("<II", len(records), 0))
        for rec in records:
            rec_id, cid, tname, pool, outcome, dur, flags, ts = rec
            cid_b = cid.encode('ascii').ljust(16, b'\0')[:16]
            tname_b = tname.encode('ascii').ljust(64, b'\0')[:64]
            pool_b = pool.encode('ascii').ljust(24, b'\0')[:24]
            f.write(struct.pack("<Q16s64s24sBIBQ", rec_id, cid_b, tname_b, pool_b, outcome, dur, flags, ts))

def run_query_suite(conn):
    c = conn.cursor()
    # Q1: Flaky tests
    c.execute("""
        WITH commit_stats AS (
            SELECT
                test_name,
                commit_hash,
                MAX(CASE WHEN outcome = 'PASSED' THEN 1 ELSE 0 END) as has_pass,
                MAX(CASE WHEN outcome = 'FAILED' THEN 1 ELSE 0 END) as has_fail
            FROM test_events
            WHERE timestamp >= 1700000000000
            GROUP BY test_name, commit_hash
        )
        SELECT
            test_name,
            ROUND(CAST(SUM(CASE WHEN has_pass = 1 AND has_fail = 1 THEN 1 ELSE 0 END) AS REAL) / COUNT(*), 4) as flake_rate,
            COUNT(*) as total_commits
        FROM commit_stats
        GROUP BY test_name
        HAVING COUNT(*) >= 5
        ORDER BY flake_rate DESC, test_name ASC
        LIMIT 10;
    """)
    cols1 = [d[0] for d in c.description]
    q1_res = [dict(zip(cols1, row)) for row in c.fetchall()]
    
    # Q2: Runner P95
    c.execute("""
        WITH ranked_durations AS (
            SELECT
                runner_pool,
                duration_us,
                ROW_NUMBER() OVER (PARTITION BY runner_pool ORDER BY duration_us) as rk,
                COUNT(*) OVER (PARTITION BY runner_pool) as total_runs
            FROM test_events
            WHERE outcome = 'PASSED' AND timestamp >= 1700000000000
        )
        SELECT
            runner_pool,
            duration_us as p95_duration_us
        FROM ranked_durations
        WHERE rk = CAST(0.95 * total_runs AS INT)
        ORDER BY runner_pool ASC;
    """)
    cols2 = [d[0] for d in c.description]
    q2_res = [dict(zip(cols2, row)) for row in c.fetchall()]
    
    # Q3: Slowdown regression
    c.execute("""
        WITH baseline AS (
            SELECT
                test_name,
                AVG(duration_us) as avg_base_us
            FROM test_events
            WHERE outcome = 'PASSED' AND timestamp >= 1700000000000
            GROUP BY test_name
        ),
        commit_durations AS (
            SELECT
                t.test_name,
                t.commit_hash,
                AVG(t.duration_us) as avg_commit_us
            FROM test_events t
            WHERE t.outcome = 'PASSED' AND t.timestamp >= 1700000000000
            GROUP BY t.test_name, t.commit_hash
        )
        SELECT
            c.test_name,
            c.commit_hash,
            ROUND(c.avg_commit_us, 2) as commit_avg_us,
            ROUND(b.avg_base_us, 2) as baseline_avg_us,
            ROUND(c.avg_commit_us - b.avg_base_us, 2) as regression_delta_us
        FROM commit_durations c
        JOIN baseline b ON c.test_name = b.test_name
        WHERE (c.avg_commit_us - b.avg_base_us) > 100000
        ORDER BY regression_delta_us DESC, c.test_name ASC, c.commit_hash ASC
        LIMIT 10;
    """)
    cols3 = [d[0] for d in c.description]
    q3_res = [dict(zip(cols3, row)) for row in c.fetchall()]
    
    # Q4: Stage attribution
    c.execute("""
        SELECT
            runner_pool,
            COUNT(*) as total_runs,
            SUM(CASE WHEN outcome = 'FAILED' THEN 1 ELSE 0 END) as failed_runs,
            ROUND(CAST(SUM(CASE WHEN outcome = 'FAILED' THEN 1 ELSE 0 END) AS REAL) / COUNT(*), 4) as failure_rate
        FROM test_events
        WHERE timestamp >= 1700000000000
        GROUP BY runner_pool
        ORDER BY runner_pool ASC;
    """)
    cols4 = [d[0] for d in c.description]
    q4_res = [dict(zip(cols4, row)) for row in c.fetchall()]
    
    return {
        "q1_flaky_tests": q1_res,
        "q2_runner_p95": q2_res,
        "q3_slowdown_regression": q3_res,
        "q4_stage_attribution": q4_res
    }

def generate_all(out_dir, sample_dir, reference_json_path, sample_json_path, seed=42):
    pools, pool_dur_mult, test_names, commits, flaky_tests, broken_commits, regression_commits = create_generator(seed)
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(sample_dir, exist_ok=True)
    
    num_shards = 32
    recs_per_shard = 5625
    base_ts = 1700000000000 # ms
    
    rec_id = 1
    all_valid_records = []
    
    test_base_dur = {}
    for i, tname in enumerate(test_names):
        test_base_dur[tname] = 300000 + (i * 45000)

    for s in range(num_shards):
        shard_records = []
        is_v2 = (s >= 16)
        for _ in range(recs_per_shard):
            cid = random.choice(commits)
            tname = random.choice(test_names)
            pool = random.choice(pools)
            
            r = random.random()
            if r < 0.04:
                flags = 0x01 # infra fault
                outcome = 1  # FAILED
            elif r < 0.08:
                flags = 0x04 # superseded/aborted
                outcome = random.choice([0, 1])
            elif r < 0.12:
                flags = 0x06 # speculative + superseded
                outcome = random.choice([0, 1])
            elif r < 0.16:
                flags = 0x02 # speculative valid
                outcome = 0 if random.random() < 0.95 else 1
            else:
                flags = 0
                if (tname, cid) in broken_commits:
                    outcome = 1
                elif tname in flaky_tests:
                    outcome = 1 if random.random() < 0.40 else 0
                else:
                    outcome = 0 if random.random() < 0.995 else 1
                    
                if random.random() < 0.01:
                    outcome = 2 # SKIPPED
                    
            b_dur = test_base_dur[tname]
            mult = pool_dur_mult[pool]
            extra = regression_commits.get((tname, cid), 0)
            noise = random.randint(-25000, 25000)
            dur = max(10000, int((b_dur + extra + noise) * mult))
            
            ts_offset = random.randint(0, 86400 * 5 * 1000)
            ts_ms = base_ts + ts_offset
            if is_v2:
                ts = ts_ms * 1000 + random.randint(0, 999)
            else:
                ts = ts_ms
                
            rec = (rec_id, cid, tname, pool, outcome, dur, flags, ts)
            shard_records.append(rec)
            
            if (flags & 5) == 0 and outcome != 2:
                all_valid_records.append((
                    rec_id, cid, tname, pool,
                    "PASSED" if outcome == 0 else "FAILED",
                    dur,
                    ts_ms
                ))
            rec_id += 1
        write_shard(os.path.join(out_dir, f"shard_{s:02d}.dat"), shard_records)
        
    # Generate sample shard (2000 legacy records, flags=0, outcome != 2)
    sample_records = []
    sample_valid = []
    for _ in range(2000):
        cid = random.choice(commits[:10])
        tname = random.choice(test_names[:10])
        pool = random.choice(pools)
        flags = 0
        outcome = 0 if random.random() < 0.92 else 1
        dur = int((test_base_dur[tname] + random.randint(-15000, 15000)) * pool_dur_mult[pool])
        ts_ms = base_ts + random.randint(0, 86400 * 3 * 1000)
        sample_records.append((rec_id, cid, tname, pool, outcome, dur, flags, ts_ms))
        sample_valid.append((rec_id, cid, tname, pool, "PASSED" if outcome == 0 else "FAILED", dur, ts_ms))
        rec_id += 1
    write_shard(os.path.join(sample_dir, "sample_01.dat"), sample_records)
    
    def compute_and_save(valid_rows, json_out):
        conn = sqlite3.connect(":memory:")
        c = conn.cursor()
        c.execute("""
            CREATE TABLE test_events (
                record_id INTEGER PRIMARY KEY,
                commit_hash TEXT NOT NULL,
                test_name TEXT NOT NULL,
                runner_pool TEXT NOT NULL,
                outcome TEXT NOT NULL,
                duration_us INTEGER NOT NULL,
                timestamp INTEGER NOT NULL
            );
        """)
        c.executemany("""
            INSERT INTO test_events VALUES (?, ?, ?, ?, ?, ?, ?);
        """, valid_rows)
        
        metrics = run_query_suite(conn)
        os.makedirs(os.path.dirname(os.path.abspath(json_out)), exist_ok=True)
        with open(json_out, "w") as f:
            json.dump(metrics, f, indent=2)
        conn.close()
        return metrics

    compute_and_save(all_valid_records, reference_json_path)
    compute_and_save(sample_valid, sample_json_path)
    print("Production shards and reference metrics generated successfully.")

if __name__ == "__main__":
    out_shards = sys.argv[1] if len(sys.argv) > 1 else "/var/lib/build_data/shards"
    sample_shards = sys.argv[2] if len(sys.argv) > 2 else "/workspace/sample_data"
    ref_json = sys.argv[3] if len(sys.argv) > 3 else "/workspace/metrics/reference_metrics.json"
    sample_json = sys.argv[4] if len(sys.argv) > 4 else "/workspace/sample_data/sample_metrics.json"
    generate_all(out_shards, sample_shards, ref_json, sample_json)
