// TCP query handler - serves JSON responses for aggregated flow data
use std::net::{TcpListener, TcpStream};
use std::io::{BufRead, BufReader, Write};
use std::sync::{Arc, Mutex};
use std::net::Ipv4Addr;
use std::str::FromStr;
use serde::{Deserialize, Serialize};
use crate::aggregator::FlowStore;

#[derive(Debug, Deserialize)]
struct QueryRequest {
    query: String,
    limit: Option<usize>,
    proto: Option<u8>,
    src_prefix: Option<String>,
}

#[derive(Debug, Serialize)]
struct FlowEntry {
    src_ip: String,
    dst_ip: String,
    proto: u8,
    packets: u64,
    bytes: u64,
}

#[derive(Debug, Serialize)]
struct QueryResponse {
    flows: Vec<FlowEntry>,
}

pub fn run(port: u16, store: Arc<Mutex<FlowStore>>) {
    let addr = format!("0.0.0.0:{}", port);
    let listener = TcpListener::bind(&addr).expect("Failed to bind TCP socket");
    eprintln!("TCP query server bound to {}", addr);

    for stream in listener.incoming() {
        match stream {
            Ok(s) => {
                let store_clone = Arc::clone(&store);
                std::thread::spawn(move || {
                    handle_client(s, store_clone);
                });
            }
            Err(e) => {
                eprintln!("TCP accept error: {}", e);
            }
        }
    }
}

fn handle_client(mut stream: TcpStream, store: Arc<Mutex<FlowStore>>) {
    let reader = BufReader::new(stream.try_clone().unwrap());
    for line in reader.lines() {
        let line = match line {
            Ok(l) => l,
            Err(_) => break,
        };
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        let req: QueryRequest = match serde_json::from_str(trimmed) {
            Ok(r) => r,
            Err(e) => {
                let err = format!("{{\"error\":\"invalid request: {}\"}}", e);
                let _ = stream.write_all(err.as_bytes());
                let _ = stream.write_all(b"\n");
                continue;
            }
        };

        let response = {
            let st = store.lock().unwrap();
            match req.query.as_str() {
                "top_talkers" => {
                    let limit = req.limit.unwrap_or(10);
                    let flows = st.get_all_sorted_by_bytes();
                    let entries: Vec<FlowEntry> = flows.into_iter().take(limit).map(|f| FlowEntry {
                        src_ip: f.key.src_ip.to_string(),
                        dst_ip: f.key.dst_ip.to_string(),
                        proto: f.key.proto,
                        packets: f.packets,
                        bytes: f.bytes,
                    }).collect();
                    QueryResponse { flows: entries }
                }
                "by_proto" => {
                    let proto = req.proto.unwrap_or(0);
                    let flows = st.get_by_proto(proto);
                    let entries: Vec<FlowEntry> = flows.into_iter().map(|f| FlowEntry {
                        src_ip: f.key.src_ip.to_string(),
                        dst_ip: f.key.dst_ip.to_string(),
                        proto: f.key.proto,
                        packets: f.packets,
                        bytes: f.bytes,
                    }).collect();
                    QueryResponse { flows: entries }
                }
                "src_filter" => {
                    let prefix_str = req.src_prefix.as_deref().unwrap_or("0.0.0.0/0");
                    let flows = parse_cidr_and_filter(&st, prefix_str);
                    let entries: Vec<FlowEntry> = flows.into_iter().map(|f| FlowEntry {
                        src_ip: f.key.src_ip.to_string(),
                        dst_ip: f.key.dst_ip.to_string(),
                        proto: f.key.proto,
                        packets: f.packets,
                        bytes: f.bytes,
                    }).collect();
                    QueryResponse { flows: entries }
                }
                _ => QueryResponse { flows: vec![] },
            }
        };

        let json = serde_json::to_string(&response).unwrap();
        let _ = stream.write_all(json.as_bytes());
        let _ = stream.write_all(b"\n");
    }
}

fn parse_cidr_and_filter(
    st: &FlowStore,
    prefix_str: &str,
) -> Vec<crate::aggregator::AggregatedFlow> {
    let parts: Vec<&str> = prefix_str.splitn(2, '/').collect();
    let addr = Ipv4Addr::from_str(parts[0]).unwrap_or(Ipv4Addr::new(0, 0, 0, 0));
    let prefix_len: u8 = if parts.len() == 2 {
        parts[1].parse().unwrap_or(0)
    } else {
        32
    };
    st.get_by_src_prefix(addr, prefix_len)
}
