// UDP listener for NetFlow v9 datagrams
use std::net::UdpSocket;
use std::sync::{Arc, Mutex};
use std::collections::HashMap;
use crate::parser::{Template, parse_datagram};
use crate::aggregator::FlowStore;

pub fn run(
    port: u16,
    store: Arc<Mutex<FlowStore>>,
    registry: Arc<Mutex<HashMap<u16, Template>>>,
) {
    let addr = format!("0.0.0.0:{}", port);
    let socket = UdpSocket::bind(&addr).expect("Failed to bind UDP socket");
    socket.set_read_timeout(None).unwrap();

    eprintln!("UDP listener bound to {}", addr);

    let mut buf = vec![0u8; 65535];
    loop {
        match socket.recv_from(&mut buf) {
            Ok((len, _src)) => {
                let data = &buf[..len];
                match parse_datagram(data, &registry) {
                    Ok(parsed) => {
                        let mut st = store.lock().unwrap();
                        for rec in &parsed.records {
                            st.ingest(rec);
                        }
                    }
                    Err(e) => {
                        eprintln!("Parse error: {}", e);
                    }
                }
            }
            Err(e) => {
                eprintln!("UDP recv error: {}", e);
                break;
            }
        }
    }
}
