// UDP listener for NetFlow v9 datagrams
// Receives datagrams on the configured port and feeds them to the parser
// and aggregator.

use std::net::UdpSocket;
use std::sync::{Arc, Mutex};

use crate::aggregator::Aggregator;
use crate::parser;

/// Maximum UDP datagram size we will accept
const MAX_DATAGRAM_SIZE: usize = 65536;

/// Statistics tracked by the UDP listener
#[derive(Debug, Default)]
pub struct ListenerStats {
    pub datagrams_received: u64,
    pub datagrams_parsed: u64,
    pub datagrams_error: u64,
    pub flows_extracted: u64,
}

/// Run the UDP listener loop. Blocks indefinitely.
///
/// Each received datagram is parsed with parser::parse_datagram and the
/// resulting flow records are forwarded to the aggregator.
pub fn run_udp_listener(
    addr: &str,
    aggregator: Arc<Mutex<Aggregator>>,
) {
    let socket = UdpSocket::bind(addr)
        .unwrap_or_else(|e| panic!("Failed to bind UDP socket {}: {}", addr, e));

    let mut buf = vec![0u8; MAX_DATAGRAM_SIZE];
    let mut stats = ListenerStats::default();

    loop {
        let (n, _src_addr) = match socket.recv_from(&mut buf) {
            Ok(r) => r,
            Err(e) => {
                eprintln!("UDP recv error: {}", e);
                continue;
            }
        };

        stats.datagrams_received += 1;
        let datagram = &buf[..n];

        match parser::parse_datagram(datagram) {
            Ok(parsed) => {
                stats.datagrams_parsed += 1;
                let flow_count = parsed.flows.len();

                if flow_count > 0 {
                    let mut agg = aggregator.lock().unwrap();
                    for flow in parsed.flows {
                        agg.record_flow(
                            flow.src_ip,
                            flow.dst_ip,
                            flow.proto,
                            flow.packets,
                            flow.bytes,
                        );
                    }
                    stats.flows_extracted += flow_count as u64;
                }

                if !parsed.templates.is_empty() {
                    // Template records found in this datagram:
                    // counted for diagnostics.
                    let _template_count = parsed.templates.len();
                }
            }
            Err(e) => {
                stats.datagrams_error += 1;
                eprintln!("Parse error for datagram from {}: {}",
                    "unknown", e);
            }
        }

        // Periodically log stats (every 1000 datagrams)
        if stats.datagrams_received % 1000 == 0 {
            eprintln!(
                "UDP stats: recv={} parsed={} err={} flows={}",
                stats.datagrams_received,
                stats.datagrams_parsed,
                stats.datagrams_error,
                stats.flows_extracted,
            );
        }
    }
}
