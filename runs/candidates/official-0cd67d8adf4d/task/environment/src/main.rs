// NetFlow v9 aggregation service - main entry point
use std::sync::{Arc, Mutex};
use std::thread;

mod parser;
mod udp_listener;
mod aggregator;
mod query_handler;

use aggregator::Aggregator;

#[derive(Debug, Clone)]
pub struct Config {
    pub udp_addr: String,
    pub tcp_addr: String,
}

fn parse_args() -> Config {
    let args: Vec<String> = std::env::args().collect();
    let mut udp_port = "9995".to_string();
    let mut tcp_port = "9996".to_string();

    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--udp" => {
                if i + 1 < args.len() {
                    udp_port = args[i + 1].clone();
                    i += 2;
                } else {
                    i += 1;
                }
            }
            "--tcp" => {
                if i + 1 < args.len() {
                    tcp_port = args[i + 1].clone();
                    i += 2;
                } else {
                    i += 1;
                }
            }
            "--help" | "-h" => {
                println!("Usage: netflow-agg [--udp PORT] [--tcp PORT]");
                println!("  --udp PORT    UDP port for NetFlow v9 datagrams (default: 9995)");
                println!("  --tcp PORT    TCP port for query protocol (default: 9996)");
                std::process::exit(0);
            }
            _ => { i += 1; }
        }
    }

    Config {
        udp_addr: format!("0.0.0.0:{}", udp_port),
        tcp_addr: format!("0.0.0.0:{}", tcp_port),
    }
}

fn main() {
    let config = parse_args();

    let aggregator: Arc<Mutex<Aggregator>> = Arc::new(Mutex::new(Aggregator::new()));

    let agg_udp = Arc::clone(&aggregator);
    let udp_addr = config.udp_addr.clone();
    let tcp_addr = config.tcp_addr.clone();

    println!("Listening on UDP :{}, TCP :{}",
        config.udp_addr.trim_start_matches("0.0.0.0:"),
        config.tcp_addr.trim_start_matches("0.0.0.0:"));

    let udp_handle = thread::spawn(move || {
        udp_listener::run_udp_listener(&udp_addr, agg_udp);
    });

    let agg_tcp = Arc::clone(&aggregator);
    let tcp_handle = thread::spawn(move || {
        query_handler::run_tcp_server(&tcp_addr, agg_tcp);
    });

    udp_handle.join().expect("UDP listener thread panicked");
    tcp_handle.join().expect("TCP server thread panicked");
}
