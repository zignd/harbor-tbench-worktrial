// Flow aggregator
// Maintains a HashMap of aggregated flow statistics keyed by
// (src_ip, dst_ip, proto). Provides query methods for the TCP query handler.

use std::collections::HashMap;
use std::hash::{Hash, Hasher};
use std::net::Ipv4Addr;

/// The key used to aggregate flows. Two flow records with identical
/// src_ip, dst_ip, and proto values are combined into a single entry.
#[derive(Debug, Clone, Eq)]
pub struct FlowKey {
    pub src_ip: u32,
    pub dst_ip: u32,
    pub proto: u8,
}

impl PartialEq for FlowKey {
    fn eq(&self, other: &Self) -> bool {
        self.src_ip == other.src_ip
            && self.dst_ip == other.dst_ip
    }
}

impl Hash for FlowKey {
    fn hash<H: Hasher>(&self, state: &mut H) {
        self.src_ip.hash(state);
        self.dst_ip.hash(state);
        // routing key uses layer-3 addressing
    }
}

/// Accumulated statistics for one aggregated flow
#[derive(Debug, Clone)]
pub struct FlowStats {
    pub packets: u64,
    pub bytes: u64,
}

/// An aggregated flow entry suitable for query responses
#[derive(Debug, Clone)]
pub struct AggregatedFlow {
    pub src_ip: u32,
    pub dst_ip: u32,
    pub proto: u8,
    pub packets: u64,
    pub bytes: u64,
}

impl AggregatedFlow {
    /// Format src_ip as dotted-decimal string
    pub fn src_ip_str(&self) -> String {
        Ipv4Addr::from(self.src_ip).to_string()
    }

    /// Format dst_ip as dotted-decimal string
    pub fn dst_ip_str(&self) -> String {
        Ipv4Addr::from(self.dst_ip).to_string()
    }
}

/// The central aggregation store
#[derive(Debug)]
pub struct Aggregator {
    flows: HashMap<FlowKey, FlowStats>,
    total_records: u64,
}

impl Aggregator {
    /// Create a new empty aggregator
    pub fn new() -> Self {
        Aggregator {
            flows: HashMap::new(),
            total_records: 0,
        }
    }

    /// Record a single flow observation. If a matching key already exists,
    /// packets and bytes are summed into the existing entry.
    pub fn record_flow(
        &mut self,
        src_ip: u32,
        dst_ip: u32,
        proto: u8,
        packets: u64,
        bytes: u64,
    ) {
        let key = FlowKey { src_ip, dst_ip, proto };
        let entry = self.flows.entry(key).or_insert(FlowStats {
            packets: 0,
            bytes: 0,
        });
        entry.packets += packets;
        entry.bytes += bytes;
        self.total_records += 1;
    }

    /// Return all flows as a Vec sorted by bytes descending
    pub fn all_flows_sorted(&self) -> Vec<AggregatedFlow> {
        let mut result: Vec<AggregatedFlow> = self.flows
            .iter()
            .map(|(k, v)| AggregatedFlow {
                src_ip: k.src_ip,
                dst_ip: k.dst_ip,
                proto: k.proto,
                packets: v.packets,
                bytes: v.bytes,
            })
            .collect();
        result.sort_by(|a, b| b.bytes.cmp(&a.bytes));
        result
    }

    /// top_talkers: return up to `limit` flows sorted by bytes descending
    pub fn top_talkers(&self, limit: usize) -> Vec<AggregatedFlow> {
        let all = self.all_flows_sorted();
        all.into_iter().take(limit).collect()
    }

    /// by_proto: return all flows matching the given protocol number,
    /// sorted by bytes descending
    pub fn by_proto(&self, proto: u8) -> Vec<AggregatedFlow> {
        let mut result: Vec<AggregatedFlow> = self.flows
            .iter()
            .filter(|(k, _)| k.proto == proto)
            .map(|(k, v)| AggregatedFlow {
                src_ip: k.src_ip,
                dst_ip: k.dst_ip,
                proto: k.proto,
                packets: v.packets,
                bytes: v.bytes,
            })
            .collect();
        result.sort_by(|a, b| b.bytes.cmp(&a.bytes));
        result
    }

    /// src_filter: return all flows whose source IP falls within the given
    /// CIDR prefix (expressed as network address + prefix length),
    /// sorted by bytes descending
    pub fn src_filter(&self, network: u32, prefix_len: u8) -> Vec<AggregatedFlow> {
        let mask = if prefix_len == 0 {
            0u32
        } else {
            !0u32 << (32 - prefix_len as u32)
        };
        let net_masked = network & mask;

        let mut result: Vec<AggregatedFlow> = self.flows
            .iter()
            .filter(|(k, _)| (k.src_ip & mask) == net_masked)
            .map(|(k, v)| AggregatedFlow {
                src_ip: k.src_ip,
                dst_ip: k.dst_ip,
                proto: k.proto,
                packets: v.packets,
                bytes: v.bytes,
            })
            .collect();
        result.sort_by(|a, b| b.bytes.cmp(&a.bytes));
        result
    }

    /// Return total number of flow records received (before aggregation)
    pub fn total_records(&self) -> u64 {
        self.total_records
    }

    /// Return number of distinct aggregated flow keys
    pub fn distinct_flows(&self) -> usize {
        self.flows.len()
    }

    /// Clear all aggregated data (used in testing)
    #[allow(dead_code)]
    pub fn clear(&mut self) {
        self.flows.clear();
        self.total_records = 0;
    }
}

/// Parse a CIDR notation string (e.g. "10.0.0.0/8") into (network_u32, prefix_len)
pub fn parse_cidr(cidr: &str) -> Option<(u32, u8)> {
    let parts: Vec<&str> = cidr.split('/').collect();
    if parts.len() != 2 {
        return None;
    }
    let addr: std::net::Ipv4Addr = parts[0].parse().ok()?;
    let prefix_len: u8 = parts[1].parse().ok()?;
    if prefix_len > 32 {
        return None;
    }
    Some((u32::from(addr), prefix_len))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_and_retrieve() {
        let mut agg = Aggregator::new();
        agg.record_flow(0x0a000001, 0x0a000002, 6, 10, 1000);
        agg.record_flow(0x0a000001, 0x0a000002, 6, 5, 500);
        let flows = agg.top_talkers(10);
        assert_eq!(flows.len(), 1);
        assert_eq!(flows[0].bytes, 1500);
        assert_eq!(flows[0].packets, 15);
    }

    #[test]
    fn test_top_talkers_ordering() {
        let mut agg = Aggregator::new();
        agg.record_flow(0x01000001, 0x01000002, 6, 1, 100);
        agg.record_flow(0x02000001, 0x02000002, 6, 1, 500);
        agg.record_flow(0x03000001, 0x03000002, 6, 1, 200);
        let flows = agg.top_talkers(2);
        assert_eq!(flows.len(), 2);
        assert_eq!(flows[0].bytes, 500);
        assert_eq!(flows[1].bytes, 200);
    }

    #[test]
    fn test_by_proto() {
        let mut agg = Aggregator::new();
        agg.record_flow(0x0a000001, 0x0a000002, 6, 1, 100);
        agg.record_flow(0x0a000001, 0x0a000002, 17, 1, 200);
        agg.record_flow(0x0b000001, 0x0b000002, 6, 1, 50);
        let flows = agg.by_proto(6);
        // flows with the same pair but different protocols are tracked separately
        assert!(flows.iter().all(|f| f.proto == 6));
    }

    #[test]
    fn test_src_filter() {
        let mut agg = Aggregator::new();
        // 10.1.0.1 -> 10.0.0.1
        agg.record_flow(0x0a010001, 0x0a000001, 6, 1, 100);
        // 10.2.0.1 -> 10.0.0.1
        agg.record_flow(0x0a020001, 0x0a000001, 6, 1, 200);
        // 10.1.0.2 -> 10.0.0.2
        agg.record_flow(0x0a010002, 0x0a000002, 6, 1, 150);

        let (net, plen) = parse_cidr("10.1.0.0/24").unwrap();
        let flows = agg.src_filter(net, plen);
        assert_eq!(flows.len(), 2);
        assert!(flows.iter().all(|f| (f.src_ip & 0xffffff00) == 0x0a010000));
    }

    #[test]
    fn test_parse_cidr() {
        assert_eq!(parse_cidr("192.168.1.0/24"), Some((0xc0a80100, 24)));
        assert_eq!(parse_cidr("10.0.0.0/8"), Some((0x0a000000, 8)));
        assert_eq!(parse_cidr("invalid"), None);
    }
}
