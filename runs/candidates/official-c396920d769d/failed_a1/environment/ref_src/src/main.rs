// Reference accumulator binary - correct fixed-point implementation
use std::io::{BufReader, Read};
use std::fs::File;
use rusqlite::{Connection, params};

const SCALE: i64 = 1i64 << 16;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 3 {
        eprintln!("Usage: accumulator_ref <input.bin> <output.db>");
        std::process::exit(1);
    }
    let batches = parse_batches(&args[1]).expect("parse");
    let conn = Connection::open(&args[2]).expect("db open");
    conn.execute_batch("
        CREATE TABLE IF NOT EXISTS results (
            batch_id INTEGER,
            sample_count INTEGER,
            fixed_mean INTEGER,
            fixed_variance INTEGER,
            checksum INTEGER
        );
        DELETE FROM results;
    ").expect("init");
    for b in &batches {
        let (fm, fv, ck) = compute_stats(&b.samples);
        conn.execute(
            "INSERT INTO results (batch_id, sample_count, fixed_mean, fixed_variance, checksum) VALUES (?1,?2,?3,?4,?5)",
            params![b.batch_id, b.samples.len() as i64, fm, fv, ck],
        ).expect("insert");
    }
}

struct Batch { batch_id: i64, samples: Vec<i32> }

fn parse_batches(path: &str) -> std::io::Result<Vec<Batch>> {
    let mut r = BufReader::new(File::open(path)?);
    let mut out = Vec::new();
    loop {
        let mut h = [0u8; 8];
        match r.read_exact(&mut h) {
            Ok(_) => {}
            Err(e) if e.kind() == std::io::ErrorKind::UnexpectedEof => break,
            Err(e) => return Err(e),
        }
        let batch_id = i32::from_le_bytes([h[0],h[1],h[2],h[3]]) as i64;
        let count = i32::from_le_bytes([h[4],h[5],h[6],h[7]]) as usize;
        let mut samples = Vec::with_capacity(count);
        for _ in 0..count {
            let mut b = [0u8;4];
            r.read_exact(&mut b)?;
            samples.push(i32::from_le_bytes(b));
        }
        out.push(Batch { batch_id, samples });
    }
    Ok(out)
}

fn compute_stats(samples: &[i32]) -> (i64, i64, i64) {
    let n = samples.len() as i64;
    if n == 0 { return (0, 0, 0); }

    let sum: i64 = samples.iter().map(|&x| x as i64).sum();

    // fixed_mean: Q16.16 representation of (sum/n), rounded half-up
    // = floor(sum * SCALE / n + 0.5)
    // Implemented as: divide with round-half-up
    let numer = sum * SCALE;
    let q = numer / n;
    let r = numer % n;
    // round-half-up: if 2*|r| >= n, round away from zero in direction of remainder
    let fixed_mean = if 2 * r.abs() >= n {
        if r >= 0 { q + 1 } else { q - 1 }
    } else {
        q
    };

    // fixed_variance: Q16.16 representation of population variance, truncated (floor toward zero)
    // variance = sum((x - true_mean)^2) / n
    // In Q16.16: compute using the mean in Q16.16
    // diff_q = x*SCALE - fixed_mean  (Q16.16)
    // sum(diff_q^2) is Q32.32
    // divide by SCALE*n to get Q16.16, truncate
    let mut sum_sq: i128 = 0;
    for &x in samples {
        let diff = (x as i128) * (SCALE as i128) - (fixed_mean as i128);
        sum_sq += diff * diff;
    }
    let denom = (SCALE as i128) * (n as i128);
    let fixed_variance = (sum_sq / denom) as i64;

    // checksum: CRC32 of raw i32 samples in little-endian order (IEEE polynomial)
    let mut hasher = crc32fast::Hasher::new();
    for &x in samples {
        hasher.update(&x.to_le_bytes());
    }
    let checksum = hasher.finalize() as i64;

    (fixed_mean, fixed_variance, checksum)
}
