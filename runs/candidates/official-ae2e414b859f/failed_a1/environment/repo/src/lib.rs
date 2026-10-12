pub mod codec;
pub mod frame;

use codec::Packet;
use frame::Frame;
use std::io::Cursor;

/// Encode a packet into a length-framed buffer.
pub fn encode_packet(pkt: &Packet) -> std::io::Result<Vec<u8>> {
    let mut payload = Vec::new();
    pkt.encode(&mut payload)?;
    let frame = Frame::new(payload);
    let mut out = Vec::new();
    frame.encode(&mut out)?;
    Ok(out)
}

/// Decode a packet from a length-framed buffer.
pub fn decode_packet(data: &[u8]) -> std::io::Result<Packet> {
    let mut cursor = Cursor::new(data);
    let frame = Frame::decode(&mut cursor)?;
    let mut payload_cursor = Cursor::new(frame.payload);
    Packet::decode(&mut payload_cursor)
}
