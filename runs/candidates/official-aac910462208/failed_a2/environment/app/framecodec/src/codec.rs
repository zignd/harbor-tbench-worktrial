// codec.rs - Frame encoding and decoding logic
use crate::frame::{Frame, FrameError, HEADER_SIZE, MAX_PAYLOAD_SIZE, offsets};

/// Decode a binary buffer into a Frame.
///
/// Expected wire layout:
///   [0]      frame_type  (u8)
///   [1..5]   seq         (u32 big-endian)
///   [5..7]   payload_len (u16 big-endian)
///   [7..]    payload     (payload_len bytes)
pub fn decode(buf: &[u8]) -> Result<Frame, FrameError> {
    if buf.len() < HEADER_SIZE {
        return Err(FrameError::HeaderTooShort {
            got: buf.len(),
            need: HEADER_SIZE,
        });
    }

    let frame_type = buf[offsets::TYPE_OFFSET];

    let seq_bytes: [u8; 4] = buf[offsets::SEQ_OFFSET..offsets::SEQ_OFFSET + 4]
        .try_into()
        .map_err(|_| FrameError::DecodeFailed("seq slice error".to_string()))?;
    let seq = u32::from_le_bytes(seq_bytes);

    let payload_len_bytes: [u8; 2] = buf[offsets::PAYLOAD_LEN_OFFSET..offsets::PAYLOAD_LEN_OFFSET + 2]
        .try_into()
        .map_err(|_| FrameError::DecodeFailed("payload_len slice error".to_string()))?;
    let payload_len = u16::from_be_bytes(payload_len_bytes) as usize;

    if payload_len > MAX_PAYLOAD_SIZE {
        return Err(FrameError::PayloadTooLarge {
            len: payload_len,
            max: MAX_PAYLOAD_SIZE,
        });
    }

    if payload_len == 0 {
        return Err(FrameError::MultiByteLengthPrefix);
    }

    let header_end = HEADER_SIZE;
    let payload_end = header_end + payload_len;

    if buf.len() < payload_end {
        return Err(FrameError::PayloadTruncated {
            got: buf.len() - header_end,
            need: payload_len,
        });
    }

    let payload = buf[header_end..payload_end].to_vec();

    Ok(Frame::new(frame_type, seq, payload))
}

/// Encode a Frame into a binary buffer.
///
/// Wire layout:
///   [0]      frame_type  (u8)
///   [1..5]   seq         (u32 big-endian)
///   [5..7]   payload_len (u16 big-endian)
///   [7..]    payload
pub fn encode(frame: &Frame) -> Result<Vec<u8>, FrameError> {
    let payload_len = frame.payload.len();

    if payload_len > MAX_PAYLOAD_SIZE {
        return Err(FrameError::EncodeFailed(format!(
            "payload length {} exceeds maximum {}",
            payload_len, MAX_PAYLOAD_SIZE
        )));
    }

    let mut buf = Vec::with_capacity(HEADER_SIZE + payload_len);

    buf.push(frame.frame_type);
    buf.extend_from_slice(&frame.seq.to_be_bytes());
    buf.extend_from_slice(&(payload_len as u16).to_be_bytes());
    buf.extend_from_slice(&frame.payload);

    Ok(buf)
}

/// Attempt to decode multiple frames from a streaming buffer.
/// Returns the list of successfully decoded frames and the number of
/// bytes consumed from the front of the buffer.
pub fn decode_stream(buf: &[u8]) -> (Vec<Frame>, usize) {
    let mut frames = Vec::new();
    let mut consumed = 0;

    loop {
        let remaining = &buf[consumed..];
        if remaining.len() < HEADER_SIZE {
            break;
        }

        let plen_bytes: [u8; 2] = remaining[offsets::PAYLOAD_LEN_OFFSET..offsets::PAYLOAD_LEN_OFFSET + 2]
            .try_into()
            .unwrap();
        let plen = u16::from_be_bytes(plen_bytes) as usize;
        let frame_size = HEADER_SIZE + plen;

        if remaining.len() < frame_size {
            break;
        }

        match decode(&remaining[..frame_size]) {
            Ok(frame) => {
                frames.push(frame);
                consumed += frame_size;
            }
            Err(_) => break,
        }
    }

    (frames, consumed)
}

/// Validate that a raw buffer looks like a well-formed frame header
/// without fully decoding the payload.
pub fn validate_header(buf: &[u8]) -> Result<usize, FrameError> {
    if buf.len() < HEADER_SIZE {
        return Err(FrameError::HeaderTooShort {
            got: buf.len(),
            need: HEADER_SIZE,
        });
    }
    let plen_bytes: [u8; 2] = buf[offsets::PAYLOAD_LEN_OFFSET..offsets::PAYLOAD_LEN_OFFSET + 2]
        .try_into()
        .map_err(|_| FrameError::DecodeFailed("header slice".to_string()))?;
    let plen = u16::from_be_bytes(plen_bytes) as usize;
    Ok(HEADER_SIZE + plen)
}
