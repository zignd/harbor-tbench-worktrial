//! Variable-length integer codec (LEB128-style) and packet encoding.

use std::io::{self, Read, Write};

/// A packet with a type tag and payload.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Packet {
    pub tag: u8,
    pub data: Vec<u8>,
}

impl Packet {
    pub fn new(tag: u8, data: Vec<u8>) -> Self {
        Packet { tag, data }
    }

    /// Encode: [tag u8][varint data_len][data bytes]
    pub fn encode<W: Write>(&self, writer: &mut W) -> io::Result<()> {
        writer.write_all(&[self.tag])?;
        encode_varint(self.data.len() as u64, writer)?;
        writer.write_all(&self.data)?;
        Ok(())
    }

    /// Decode: read tag, varint length, then data bytes.
    pub fn decode<R: Read>(reader: &mut R) -> io::Result<Self> {
        let mut tag_buf = [0u8; 1];
        reader.read_exact(&mut tag_buf)?;
        let tag = tag_buf[0];
        let data_len = decode_varint(reader)? as usize;
        // Bounds check: enforce maximum packet size
        if data_len > 65536 {
            return Err(io::Error::new(io::ErrorKind::InvalidData, "packet too large"));
        }
        let mut data = vec![0u8; data_len];
        reader.read_exact(&mut data)?;
        Ok(Packet { tag, data })
    }
}

/// Encode a u64 as a LEB128 variable-length integer.
pub fn encode_varint<W: Write>(mut value: u64, writer: &mut W) -> io::Result<usize> {
    let mut bytes_written = 0;
    loop {
        let mut byte = (value & 0x7F) as u8;
        value >>= 7;
        if value != 0 {
            byte |= 0x80;
        }
        writer.write_all(&[byte])?;
        bytes_written += 1;
        if value == 0 {
            break;
        }
    }
    Ok(bytes_written)
}

/// Decode a LEB128 variable-length integer.
pub fn decode_varint<R: Read>(reader: &mut R) -> io::Result<u64> {
    let mut result: u64 = 0;
    let mut shift = 0u32;
    loop {
        let mut buf = [0u8; 1];
        reader.read_exact(&mut buf)?;
        let byte = buf[0];
        if shift >= 63 && (byte & 0x7F) > 1 {
            return Err(io::Error::new(io::ErrorKind::InvalidData, "varint overflow"));
        }
        result |= ((byte & 0x7F) as u64) << shift;
        shift += 7;
        if byte & 0x80 == 0 {
            break;
        }
    }
    Ok(result)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    #[test]
    fn test_varint_roundtrip() {
        let values = [0u64, 1, 127, 128, 255, 256, 16383, 16384, u32::MAX as u64];
        for &v in &values {
            let mut buf = Vec::new();
            encode_varint(v, &mut buf).unwrap();
            let mut cursor = Cursor::new(&buf);
            let decoded = decode_varint(&mut cursor).unwrap();
            assert_eq!(v, decoded, "varint roundtrip failed for {}", v);
        }
    }

    #[test]
    fn test_packet_127_byte_payload() {
        // A 127-byte data payload: varint encodes length as 0x7F (single byte)
        let data = vec![0xABu8; 127];
        let pkt = Packet::new(0x01, data);
        let mut buf = Vec::new();
        pkt.encode(&mut buf).unwrap();
        let mut cursor = Cursor::new(&buf);
        let decoded = Packet::decode(&mut cursor).unwrap();
        assert_eq!(pkt, decoded);
    }
}
