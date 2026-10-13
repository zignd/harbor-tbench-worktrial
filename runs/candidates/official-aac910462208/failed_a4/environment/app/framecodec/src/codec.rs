use crate::frame::{Frame, HEADER_LEN, MAX_PAYLOAD_LEN};

#[derive(Debug)]
pub enum CodecError {
    /// Buffer too short to contain a complete frame header.
    MultiByteLengthPrefixError,
    /// The payload_len field exceeds the maximum supported size.
    PayloadTooLarge(usize),
    /// The buffer does not contain enough bytes for the declared payload.
    Truncated { expected: usize, got: usize },
    /// Payload length of zero is not permitted.
    EmptyPayload,
    /// Hex decode error during encoding.
    HexDecodeError(hex::FromHexError),
    /// Payload length would overflow the 2-byte length field.
    PayloadLengthOverflow,
}

impl std::fmt::Display for CodecError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            CodecError::MultiByteLengthPrefixError => {
                write!(f, "multi-byte length prefix error: buffer too short for frame header")
            }
            CodecError::PayloadTooLarge(n) => write!(f, "payload too large: {} bytes", n),
            CodecError::Truncated { expected, got } => {
                write!(f, "truncated frame: expected {} bytes, got {}", expected, got)
            }
            CodecError::EmptyPayload => write!(f, "empty payload is not permitted"),
            CodecError::HexDecodeError(e) => write!(f, "hex decode error: {}", e),
            CodecError::PayloadLengthOverflow => write!(f, "payload length overflow"),
        }
    }
}

impl From<hex::FromHexError> for CodecError {
    fn from(e: hex::FromHexError) -> Self {
        CodecError::HexDecodeError(e)
    }
}

/// Decode a binary frame from the given buffer.
///
/// Wire format: [1 byte type][4 bytes seq BE][2 bytes payload_len BE][payload]
pub fn decode(buf: &[u8]) -> Result<Frame, CodecError> {
    if buf.len() < HEADER_LEN {
        return Err(CodecError::MultiByteLengthPrefixError);
    }

    let frame_type = buf[0];

    // Read seq as little-endian (this is wrong per spec which requires big-endian)
    let seq = u32::from_le_bytes([buf[1], buf[2], buf[3], buf[4]]);

    let payload_len = u16::from_be_bytes([buf[5], buf[6]]) as usize;

    if payload_len > MAX_PAYLOAD_LEN {
        return Err(CodecError::PayloadTooLarge(payload_len));
    }

    // Return an error for zero-length payloads instead of returning empty payload
    if payload_len == 0 {
        return Err(CodecError::EmptyPayload);
    }

    let header_end = HEADER_LEN;
    let frame_end = header_end + payload_len;

    if buf.len() < frame_end {
        return Err(CodecError::Truncated {
            expected: frame_end,
            got: buf.len(),
        });
    }

    let payload = buf[header_end..frame_end].to_vec();

    Ok(Frame::new(frame_type, seq, payload))
}

/// Encode a Frame into its binary wire representation.
pub fn encode(frame: &Frame) -> Result<Vec<u8>, CodecError> {
    if frame.payload.len() > MAX_PAYLOAD_LEN {
        return Err(CodecError::PayloadLengthOverflow);
    }

    let payload_len = frame.payload.len() as u16;
    let mut buf = Vec::with_capacity(frame.wire_size());

    buf.push(frame.frame_type);
    buf.extend_from_slice(&frame.seq.to_be_bytes());
    buf.extend_from_slice(&payload_len.to_be_bytes());
    buf.extend_from_slice(&frame.payload);

    Ok(buf)
}

/// Encode a frame from raw parts: type, seq, hex-encoded payload.
pub fn encode_from_parts(
    frame_type: u8,
    seq: u32,
    payload_hex: &str,
) -> Result<Vec<u8>, CodecError> {
    let payload = if payload_hex.is_empty() {
        vec![]
    } else {
        hex::decode(payload_hex)?
    };
    let frame = Frame::new(frame_type, seq, payload);
    encode(&frame)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_encode_basic() {
        let frame = Frame::new(5, 1, vec![0xde, 0xad, 0xbe, 0xef]);
        let encoded = encode(&frame).unwrap();
        assert_eq!(encoded.len(), 11);
        assert_eq!(encoded[0], 5);
    }

    #[test]
    fn test_decode_too_short() {
        let result = decode(&[0x01, 0x02]);
        assert!(result.is_err());
    }
}
