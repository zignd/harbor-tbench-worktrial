// NetFlow v9 packet parser
// Parses NetFlow v9 datagrams into template records and data records.

use std::collections::HashMap;

/// NetFlow v9 field type identifiers (RFC 3954)
#[allow(dead_code)]
pub mod field_type {
    pub const IN_BYTES: u16 = 1;
    pub const IN_PKTS: u16 = 2;
    pub const PROTOCOL: u16 = 4;
    pub const IPV4_SRC_ADDR: u16 = 8;
    pub const IPV4_DST_ADDR: u16 = 12;
    pub const L4_SRC_PORT: u16 = 7;
    pub const L4_DST_PORT: u16 = 11;
    pub const FIRST_SWITCHED: u16 = 22;
    pub const LAST_SWITCHED: u16 = 21;
    pub const INPUT_SNMP: u16 = 10;
    pub const OUTPUT_SNMP: u16 = 14;
    pub const SRC_TOS: u16 = 5;
    pub const TCP_FLAGS: u16 = 6;
    pub const SRC_AS: u16 = 16;
    pub const DST_AS: u16 = 17;
    pub const BGP_IPV4_NEXT_HOP: u16 = 15;
    pub const MUL_DST_PKTS: u16 = 24;
    pub const MUL_DST_BYTES: u16 = 23;
    pub const OUT_BYTES: u16 = 85;
    pub const OUT_PKTS: u16 = 86;
    pub const IPV6_SRC_ADDR: u16 = 27;
    pub const IPV6_DST_ADDR: u16 = 28;
    pub const FLOW_SAMPLER_ID: u16 = 48;
    pub const FLOW_CLASS: u16 = 51;
    pub const IF_NAME: u16 = 82;
    pub const IF_DESC: u16 = 83;
    pub const SAMPLER_NAME: u16 = 84;
    pub const IN_PERMANENT_BYTES: u16 = 85;
    pub const IN_PERMANENT_PKTS: u16 = 86;
    pub const FRAGMENT_OFFSET: u16 = 88;
    pub const FORWARDING_STATUS: u16 = 89;
    pub const MPLS_PAL_RD: u16 = 90;
    pub const MPLS_PREFIX_LEN: u16 = 91;
    pub const SRC_TRAFFIC_INDEX: u16 = 92;
    pub const DST_TRAFFIC_INDEX: u16 = 93;
}

/// A single field definition within a template
#[derive(Debug, Clone)]
pub struct FieldDef {
    pub field_type: u16,
    pub field_length: u16,
}

/// A NetFlow v9 template record
#[derive(Debug, Clone)]
pub struct Template {
    pub template_id: u16,
    pub fields: Vec<FieldDef>,
}

impl Template {
    /// Total byte length of a data record matching this template
    pub fn record_length(&self) -> usize {
        self.fields.iter().map(|f| f.field_length as usize).sum()
    }

    /// Find the offset and length of a field by type
    pub fn field_offset(&self, target_type: u16) -> Option<(usize, usize)> {
        let mut offset = 0usize;
        for field in &self.fields {
            if field.field_type == target_type {
                return Some((offset, field.field_length as usize));
            }
            offset += field.field_length as usize;
        }
        None
    }
}

/// A parsed flow record extracted from a data flowset
#[derive(Debug, Clone)]
pub struct FlowRecord {
    pub src_ip: u32,
    pub dst_ip: u32,
    pub proto: u8,
    pub packets: u64,
    pub bytes: u64,
}

/// The result of parsing one NetFlow v9 datagram
#[derive(Debug)]
pub struct ParsedDatagram {
    pub source_id: u32,
    pub seq_number: u32,
    pub templates: Vec<Template>,
    pub flows: Vec<FlowRecord>,
}

/// Error type for parsing failures
#[derive(Debug)]
pub enum ParseError {
    TooShort,
    BadVersion(u16),
    Truncated,
    InvalidTemplate,
}

impl std::fmt::Display for ParseError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ParseError::TooShort => write!(f, "datagram too short"),
            ParseError::BadVersion(v) => write!(f, "unsupported NetFlow version {}", v),
            ParseError::Truncated => write!(f, "datagram truncated"),
            ParseError::InvalidTemplate => write!(f, "invalid template record"),
        }
    }
}

pub type Result<T> = std::result::Result<T, ParseError>;

/// Read a big-endian u16 from a byte slice at offset
fn read_u16(buf: &[u8], offset: usize) -> Option<u16> {
    if offset + 2 > buf.len() {
        return None;
    }
    Some(u16::from_be_bytes([buf[offset], buf[offset + 1]]))
}

/// Read a big-endian u32 from a byte slice at offset
fn read_u32(buf: &[u8], offset: usize) -> Option<u32> {
    if offset + 4 > buf.len() {
        return None;
    }
    Some(u32::from_be_bytes([
        buf[offset], buf[offset + 1],
        buf[offset + 2], buf[offset + 3],
    ]))
}

/// Parse a template flowset (flowset_id == 0)
fn parse_template_flowset(
    data: &[u8],
    templates_out: &mut Vec<Template>,
) -> Result<()> {
    let mut pos = 0usize;
    while pos + 4 <= data.len() {
        let template_id = read_u16(data, pos).ok_or(ParseError::Truncated)?;
        let field_count = read_u16(data, pos + 2).ok_or(ParseError::Truncated)? as usize;
        pos += 4;

        if field_count == 0 {
            continue;
        }

        if pos + field_count * 4 > data.len() {
            break;
        }

        let mut fields = Vec::with_capacity(field_count);
        for _ in 0..field_count {
            let ftype = read_u16(data, pos).ok_or(ParseError::Truncated)?;
            let flen = read_u16(data, pos + 2).ok_or(ParseError::Truncated)?;
            pos += 4;
            if flen == 0 {
                return Err(ParseError::InvalidTemplate);
            }
            fields.push(FieldDef {
                field_type: ftype,
                field_length: flen,
            });
        }

        templates_out.push(Template {
            template_id,
            fields,
        });
    }
    Ok(())
}

/// Parse data records from a data flowset using a known template
fn parse_data_flowset(
    data: &[u8],
    template: &Template,
    flows_out: &mut Vec<FlowRecord>,
) {
    let rec_len = template.record_length();
    if rec_len == 0 {
        return;
    }

    let mut pos = 0usize;
    while pos + rec_len <= data.len() {
        let record = &data[pos..pos + rec_len];
        pos += rec_len;

        let src_ip = template
            .field_offset(field_type::IPV4_SRC_ADDR)
            .and_then(|(off, len)| {
                if len == 4 { read_u32(record, off) } else { None }
            })
            .unwrap_or(0);

        let dst_ip = template
            .field_offset(field_type::IPV4_DST_ADDR)
            .and_then(|(off, len)| {
                if len == 4 { read_u32(record, off) } else { None }
            })
            .unwrap_or(0);

        let proto = template
            .field_offset(field_type::PROTOCOL)
            .and_then(|(off, len)| {
                if len == 1 && off < record.len() { Some(record[off]) } else { None }
            })
            .unwrap_or(0);

        let packets: u64 = template
            .field_offset(field_type::IN_PKTS)
            .map(|(off, len)| read_variable_uint(record, off, len))
            .unwrap_or(0);

        let bytes: u64 = template
            .field_offset(field_type::IN_BYTES)
            .map(|(off, len)| read_variable_uint(record, off, len))
            .unwrap_or(0);

        if src_ip != 0 || dst_ip != 0 {
            flows_out.push(FlowRecord {
                src_ip,
                dst_ip,
                proto,
                packets,
                bytes,
            });
        }
    }
}

/// Read a big-endian unsigned integer of variable byte width
fn read_variable_uint(buf: &[u8], offset: usize, len: usize) -> u64 {
    if offset + len > buf.len() {
        return 0;
    }
    match len {
        1 => buf[offset] as u64,
        2 => u16::from_be_bytes([buf[offset], buf[offset + 1]]) as u64,
        4 => u32::from_be_bytes([
            buf[offset], buf[offset + 1],
            buf[offset + 2], buf[offset + 3],
        ]) as u64,
        8 => u64::from_be_bytes([
            buf[offset], buf[offset + 1], buf[offset + 2], buf[offset + 3],
            buf[offset + 4], buf[offset + 5], buf[offset + 6], buf[offset + 7],
        ]),
        _ => 0,
    }
}

/// Parse a complete NetFlow v9 datagram.
///
/// Parse a NetFlow v9 datagram, extracting template definitions and data records.
/// Returns a ParsedDatagram containing any templates found and any decoded flow records.
/// Templates are returned in ParsedDatagram.templates.
/// Data flowsets referencing templates not seen in this datagram produce no flow records.
pub fn parse_datagram(buf: &[u8]) -> Result<ParsedDatagram> {
    if buf.len() < 20 {
        return Err(ParseError::TooShort);
    }

    let version = read_u16(buf, 0).ok_or(ParseError::TooShort)?;
    if version != 9 {
        return Err(ParseError::BadVersion(version));
    }

    let count = read_u16(buf, 2).ok_or(ParseError::TooShort)? as usize;
    let _unix_secs = read_u32(buf, 4).ok_or(ParseError::TooShort)?;
    let seq_number = read_u32(buf, 8).ok_or(ParseError::TooShort)?;
    let source_id = read_u32(buf, 12).ok_or(ParseError::TooShort)?;

    let mut pos = 20usize;
    // Template registry for this datagram.
    let mut local_templates: HashMap<u16, Template> = HashMap::new();
    let mut new_templates = Vec::new();
    let mut flows = Vec::new();
    let mut flowsets_parsed = 0usize;

    while pos + 4 <= buf.len() && flowsets_parsed < count + 64 {
        let flowset_id = read_u16(buf, pos).ok_or(ParseError::Truncated)?;
        let flowset_length = read_u16(buf, pos + 2).ok_or(ParseError::Truncated)? as usize;

        if flowset_length < 4 {
            break;
        }
        if pos + flowset_length > buf.len() {
            break;
        }

        let flowset_data = &buf[pos + 4..pos + flowset_length];
        pos += flowset_length;
        flowsets_parsed += 1;

        if flowset_id == 0 {
            // Template flowset
            let mut parsed = Vec::new();
            parse_template_flowset(flowset_data, &mut parsed)?;
            for tmpl in parsed {
                local_templates.insert(tmpl.template_id, tmpl.clone());
                new_templates.push(tmpl);
            }
        } else if flowset_id == 1 {
            // Options template flowset — not implemented
        } else if flowset_id >= 256 {
            // Data flowset — look up template in registry
            if let Some(tmpl) = local_templates.get(&flowset_id) {
                parse_data_flowset(flowset_data, tmpl, &mut flows);
            }
            // Template not found in registry.
        }
    }

    Ok(ParsedDatagram {
        source_id,
        seq_number,
        templates: new_templates,
        flows,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_too_short() {
        let result = parse_datagram(&[0u8; 5]);
        assert!(matches!(result, Err(ParseError::TooShort)));
    }

    #[test]
    fn test_parse_bad_version() {
        let mut buf = vec![0u8; 20];
        buf[0] = 0; buf[1] = 5;
        let result = parse_datagram(&buf);
        assert!(matches!(result, Err(ParseError::BadVersion(5))));
    }

    #[test]
    fn test_field_offset() {
        let tmpl = Template {
            template_id: 256,
            fields: vec![
                FieldDef { field_type: 8, field_length: 4 },
                FieldDef { field_type: 12, field_length: 4 },
                FieldDef { field_type: 4, field_length: 1 },
            ],
        };
        assert_eq!(tmpl.field_offset(8), Some((0, 4)));
        assert_eq!(tmpl.field_offset(12), Some((4, 4)));
        assert_eq!(tmpl.field_offset(4), Some((8, 1)));
        assert_eq!(tmpl.field_offset(99), None);
    }
}
