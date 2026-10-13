mod buffer;
mod aggregator;
mod parser;

use crate::buffer::ConcurrentBuffer;
use crate::aggregator::Aggregator;
use rayon::prelude::*;
use std::fs::{self, File};
use std::io::{BufRead, BufReader};
use std::path::PathBuf;
use std::sync::Arc;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().collect();
    let input_dir = args.iter().position(|x| x == "--input").map(|i| &args[i+1]).expect("Missing --input");
    let output_path = args.iter().position(|x| x == "--output").map(|i| &args[i+1]).expect("Missing --output");

    let paths: Vec<PathBuf> = fs::read_dir(input_dir)?
        .filter_map(|e| e.ok())
        .map(|e| e.path())
        .filter(|p| p.extension().map_or(false, |ext| ext == "csv"))
        .collect();

    let chunk_size = 1024;
    let buffer = Arc::new(ConcurrentBuffer::<(String, f32)>::new(chunk_size, 20000));

    paths.par_iter().for_each(|path| {
        let file = File::open(path).unwrap();
        let reader = BufReader::new(file);
        let mut chunk = Vec::with_capacity(chunk_size);
        
        for line in reader.lines().skip(1) { // Skip header
            if let Ok(l) = line {
                if let Some(record) = parser::parse_line(&l) {
                    chunk.push(record);
                    if chunk.len() == chunk_size {
                        buffer.push_chunk(&chunk);
                        chunk.clear();
                    }
                }
            }
        }
        if !chunk.is_empty() {
            // Remaining in the last chunk
            buffer.push_chunk(&chunk);
        }
    });

    let mut aggregator = Aggregator::new();
    let data = buffer.get_data();
    let mut count = 0;
    for (region, value) in data {
        if !region.is_empty() {
            aggregator.add(region.clone(), *value);
            count += 1;
        }
    }

    println!("[INFO] Processed {} records.", count);
    let results = aggregator.get_results();
    let file = File::create(output_path)?;
    serde_json::to_writer_pretty(file, &results)?;
    println!("[INFO] Success.");

    Ok(())
}
