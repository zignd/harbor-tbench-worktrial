mod buffer;
mod aggregator;
mod parser;

use clap::Parser as ClapParser;
use rayon::prelude::*;
use std::fs::{self, File};
use std::io::{BufRead, BufReader};
use std::path::PathBuf;
use crate::buffer::ChunkedCollector;

#[derive(ClapParser)]
struct Args {
    #[arg(long)]
    input: PathBuf,
    #[arg(long)]
    output: PathBuf,
}

fn main() {
    let args = Args::parse();
    let files: Vec<PathBuf> = fs::read_dir(args.input)
        .unwrap()
        .map(|res| res.unwrap().path())
        .filter(|path| path.extension().map_or(false, |ext| ext == "csv"))
        .collect();

    let collector = ChunkedCollector::new(1024, 1024);

    files.par_iter().for_each(|path| {
        let file = File::open(path).unwrap();
        let reader = BufReader::new(file);
        let parser = parser::Parser::new();
        
        for line in reader.lines().skip(1) { // Skip header
            if let Ok(line_str) = line {
                if let Ok((region, value)) = parser.parse_line(&line_str) {
                    collector.add_record(region, value);
                }
            }
        }
    });

    let records = collector.get_all_records();
    println!("[INFO] Processed {} records.", records.len());
    
    let results = aggregator::aggregate(records);
    
    let file = File::create(args.output).unwrap();
    serde_json::to_writer_pretty(file, &results).unwrap();
    println!("[INFO] Success.");
}
