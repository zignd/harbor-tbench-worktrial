// TCP query handler
// Listens for JSON query requests on the configured TCP port and returns
// JSON responses with aggregated flow data.

use std::io::{BufRead, BufReader, Write};
use std::net::{TcpListener, TcpStream};
use std::sync::{Arc, Mutex};

use crate::aggregator::{Aggregator, AggregatedFlow, parse_cidr};

/// Maximum length of a single query line in bytes
const MAX_QUERY_LEN: usize = 4096;

/// Serialize one AggregatedFlow to a JSON object string
fn flow_to_json(f: &AggregatedFlow) -> String {
    let src = std::net::Ipv4Addr::from(f.src_ip);
    let dst = std::net::Ipv4Addr::from(f.dst_ip);
    let mut s = String::new();
    s.push('{');
    s.push_str(&format!("\"src_ip\":\"{}\"", src));
    s.push(',');
    s.push_str(&format!("\"dst_ip\":\"{}\"", dst));
    s.push(',');
    s.push_str(&format!("\"proto\":{}", f.proto));
    s.push(',');
    s.push_str(&format!("\"packets\":{}", f.packets));
    s.push(',');
    s.push_str(&format!("\"bytes\":{}", f.bytes));
    s.push('}');
    s
}

/// Serialize a slice of AggregatedFlow records to a JSON string
fn flows_to_json(flows: &[AggregatedFlow]) -> String {
    let parts: Vec<String> = flows.iter().map(flow_to_json).collect();
    let mut s = String::new();
    s.push_str("{\"flows\":[");
    s.push_str(&parts.join(","));
    s.push_str("]}");
    s
}

/// Extract a string field from a JSON object string.
/// Very simple scanner — only handles flat objects with string/number values.
fn json_get_str<'a>(json: &'a str, key: &str) -> Option<&'a str> {
    let needle = format!("\"{}\":", key);
    let pos = json.find(needle.as_str())?;
    let rest = json[pos + needle.len()..].trim_start();
    if rest.starts_with('"') {
        let inner = &rest[1..];
        let end = inner.find('"')?;
        Some(&inner[..end])
    } else {
        None
    }
}

/// Extract a number field from a JSON object string
fn json_get_u64(json: &str, key: &str) -> Option<u64> {
    let needle = format!("\"{}\":", key);
    let pos = json.find(needle.as_str())?;
    let rest = json[pos + needle.len()..].trim_start();
    let end = rest.find(|c: char| !c.is_ascii_digit()).unwrap_or(rest.len());
    if end == 0 {
        return None;
    }
    rest[..end].parse().ok()
}

/// Handle one query from a connected client
fn handle_query(line: &str, aggregator: &Arc<Mutex<Aggregator>>) -> String {
    let query_type = match json_get_str(line, "query") {
        Some(q) => q.to_string(),
        None => return "{\"error\":\"missing query field\"}\n".to_string(),
    };

    match query_type.as_str() {
        "top_talkers" => {
            let limit = json_get_u64(line, "limit").unwrap_or(10) as usize;
            let limit = if limit == 0 { 10 } else { limit };
            let agg = aggregator.lock().unwrap();
            let flows = agg.top_talkers(limit);
            format!("{}\n", flows_to_json(&flows))
        }
        "by_proto" => {
            let proto = match json_get_u64(line, "proto") {
                Some(p) if p <= 255 => p as u8,
                _ => return "{\"error\":\"missing or invalid proto field\"}\n".to_string(),
            };
            let agg = aggregator.lock().unwrap();
            let flows = agg.by_proto(proto);
            format!("{}\n", flows_to_json(&flows))
        }
        "src_filter" => {
            let prefix = match json_get_str(line, "src_prefix") {
                Some(p) => p.to_string(),
                None => return "{\"error\":\"missing src_prefix field\"}\n".to_string(),
            };
            let (network, prefix_len) = match parse_cidr(&prefix) {
                Some(cidr) => cidr,
                None => return "{\"error\":\"invalid CIDR notation\"}\n".to_string(),
            };
            let agg = aggregator.lock().unwrap();
            let flows = agg.src_filter(network, prefix_len);
            format!("{}\n", flows_to_json(&flows))
        }
        "stats" => {
            let agg = aggregator.lock().unwrap();
            format!(
                "{{\"total_records\":{},\"distinct_flows\":{}}}\n",
                agg.total_records(),
                agg.distinct_flows(),
            )
        }
        other => {
            format!("{{\"error\":\"unknown query: {}\"}}\n", other)
        }
    }
}

/// Handle a single TCP client connection
fn handle_client(stream: TcpStream, aggregator: Arc<Mutex<Aggregator>>) {
    let peer = stream.peer_addr()
        .map(|a| a.to_string())
        .unwrap_or_else(|_| "unknown".to_string());

    let mut writer = match stream.try_clone() {
        Ok(s) => s,
        Err(e) => {
            eprintln!("Failed to clone TCP stream for {}: {}", peer, e);
            return;
        }
    };

    let reader = BufReader::new(stream);

    for line_result in reader.lines() {
        let line = match line_result {
            Ok(l) => l,
            Err(_) => break,
        };
        let line = line.trim().to_string();
        if line.is_empty() {
            continue;
        }
        if line.len() > MAX_QUERY_LEN {
            let _ = writer.write_all(b"{\"error\":\"query too long\"}\n");
            continue;
        }
        let response = handle_query(&line, &aggregator);
        if writer.write_all(response.as_bytes()).is_err() {
            break;
        }
        let _ = writer.flush();
    }
}

/// Run the TCP query server loop. Blocks indefinitely.
/// Spawns a new OS thread per client connection.
pub fn run_tcp_server(addr: &str, aggregator: Arc<Mutex<Aggregator>>) {
    let listener = TcpListener::bind(addr)
        .unwrap_or_else(|e| panic!("Failed to bind TCP socket {}: {}", addr, e));

    for stream_result in listener.incoming() {
        match stream_result {
            Ok(stream) => {
                let agg = Arc::clone(&aggregator);
                std::thread::spawn(move || handle_client(stream, agg));
            }
            Err(e) => {
                eprintln!("TCP accept error: {}", e);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_json_get_str() {
        let json = "{\"query\":\"top_talkers\",\"limit\":5}";
        assert_eq!(json_get_str(json, "query"), Some("top_talkers"));
        assert_eq!(json_get_str(json, "missing"), None);
    }

    #[test]
    fn test_json_get_u64() {
        let json = "{\"query\":\"top_talkers\",\"limit\":5}";
        assert_eq!(json_get_u64(json, "limit"), Some(5));
        assert_eq!(json_get_u64(json, "query"), None);
    }

    #[test]
    fn test_flows_to_json_empty() {
        let result = flows_to_json(&[]);
        assert_eq!(result, "{\"flows\":[]}");
    }

    #[test]
    fn test_flow_to_json() {
        use crate::aggregator::AggregatedFlow;
        let flow = AggregatedFlow {
            src_ip: 0xc0a80101u32,
            dst_ip: 0x0a000001u32,
            proto: 6,
            packets: 100,
            bytes: 50000,
        };
        let s = flow_to_json(&flow);
        assert!(s.contains("192.168.1.1"), "src_ip missing: {}", s);
        assert!(s.contains("10.0.0.1"), "dst_ip missing: {}", s);
        assert!(s.contains("\"proto\":6"), "proto missing: {}", s);
        assert!(s.contains("\"bytes\":50000"), "bytes missing: {}", s);
    }
}
