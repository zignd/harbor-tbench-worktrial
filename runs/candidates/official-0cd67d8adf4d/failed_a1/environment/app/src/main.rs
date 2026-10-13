// NetFlow v9 aggregation service - main entry point
use clap::Parser;
use std::sync::{Arc, Mutex};
use std::collections::HashMap;

mod udp_listener;
mod parser;
mod aggregator;
mod query_handler;

#[derive(Parser, Debug)]
#[command(author, version, about)]
pub struct Args {
    #[arg(long, default_value = "9995")]
    pub udp: u16,
    #[arg(long, default_value = "9996")]
    pub tcp: u16,
}

fn main() {
    let args = Args::parse();

    let store = Arc::new(Mutex::new(aggregator::FlowStore::new()));
    let template_registry = Arc::new(Mutex::new(HashMap::<u16, parser::Template>::new()));

    eprintln!("Listening on UDP :{}, TCP :{}", args.udp, args.tcp);

    let store_udp = Arc::clone(&store);
    let registry_udp = Arc::clone(&template_registry);
    let udp_port = args.udp;
    let udp_thread = std::thread::spawn(move || {
        udp_listener::run(udp_port, store_udp, registry_udp);
    });

    let store_tcp = Arc::clone(&store);
    let tcp_port = args.tcp;
    let tcp_thread = std::thread::spawn(move || {
        query_handler::run(tcp_port, store_tcp);
    });

    udp_thread.join().unwrap();
    tcp_thread.join().unwrap();
}
