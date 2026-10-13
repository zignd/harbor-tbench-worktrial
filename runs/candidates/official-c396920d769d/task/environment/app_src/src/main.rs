//! Sensor pipeline entry point.
//! Reads binary batches from input, computes fixed-point statistics,
//! writes results to SQLite.

mod accumulator;
mod codec;
mod db;
mod stats;

use std::path::PathBuf;
use std::time::Instant;

use codec::BatchReader;
use db::ResultsDb;
use accumulator::BatchAccumulator;

const VERSION: &str = "0.1.0";

fn print_usage(prog: &str) {
    eprintln!("sensor-pipeline v{}", VERSION);
    eprintln!("Usage: {} <input.bin> <output.db>", prog);
    eprintln!();
    eprintln!("Reads batched sensor records from <input.bin>, computes");
    eprintln!("fixed-point statistics (Q16.16), and writes summary rows");
    eprintln!("to <output.db> (SQLite).");
    eprintln!();
    eprintln!("Environment variables:");
    eprintln!("  RUST_LOG=debug   Enable verbose logging");
}

fn main() {
    env_logger::init();

    let args: Vec<String> = std::env::args().collect();
    if args.len() != 3 {
        print_usage(&args[0]);
        std::process::exit(1);
    }

    let input_path = PathBuf::from(&args[1]);
    let output_path = PathBuf::from(&args[2]);

    if !input_path.exists() {
        eprintln!("Error: input file {:?} does not exist", input_path);
        std::process::exit(1);
    }

    log::info!("Starting pipeline: input={:?} output={:?}", input_path, output_path);

    let t0 = Instant::now();

    let reader = BatchReader::open(&input_path).unwrap_or_else(|e| {
        eprintln!("Failed to open input: {}", e);
        std::process::exit(1);
    });

    let mut db = ResultsDb::open(&output_path).unwrap_or_else(|e| {
        eprintln!("Failed to open database: {}", e);
        std::process::exit(1);
    });

    db.init_schema().unwrap_or_else(|e| {
        eprintln!("Failed to initialise schema: {}", e);
        std::process::exit(1);
    });

    let mut total_records = 0usize;
    let mut batch_count = 0usize;

    for batch_result in reader {
        let batch = batch_result.unwrap_or_else(|e| {
            eprintln!("Error reading batch: {}", e);
            std::process::exit(1);
        });

        log::debug!(
            "Processing batch {} ({} records)",
            batch.batch_id,
            batch.samples.len()
        );

        let acc = BatchAccumulator::process(&batch.samples);
        let row = acc.to_result_row(batch.batch_id);

        db.insert_row(&row).unwrap_or_else(|e| {
            eprintln!("Failed to insert row: {}", e);
            std::process::exit(1);
        });

        total_records += batch.samples.len();
        batch_count += 1;
    }

    let elapsed = t0.elapsed();
    log::info!(
        "Done: {} batches, {} records in {:.3}s",
        batch_count,
        total_records,
        elapsed.as_secs_f64()
    );

    if batch_count == 0 {
        log::warn!("No batches found in input file");
    }

    eprintln!(
        "Processed {} batches ({} records) in {:.3}s",
        batch_count,
        total_records,
        elapsed.as_secs_f64()
    );
}
