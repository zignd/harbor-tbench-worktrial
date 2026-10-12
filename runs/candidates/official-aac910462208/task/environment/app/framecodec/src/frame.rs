// frame.rs - Frame structure and wire format definitions
use std::fmt;

/// Frame type identifier byte
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct FrameType(pub u8);

impl fmt::Display for FrameType {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "FrameType({})", self.0)
    }
}

/// A decoded frame from the wire
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Frame {
    /// Frame type (1 byte)
    pub frame_type: u8,
    /// Sequence number (4 bytes, big-endian on wire)
    pub seq: u32,
    /// Payload bytes
    pub payload: Vec<u8>,
}

impl Frame {
    /// Create a new frame
    pub fn new(frame_type: u8, seq: u32, payload: Vec<u8>) -> Self {
        Frame { frame_type, seq, payload }
    }

    /// Returns the total encoded length of this frame in bytes
    pub fn encoded_len(&self) -> usize {
        HEADER_SIZE + self.payload.len()
    }

    /// Returns true if this frame has a non-empty payload
    pub fn has_payload(&self) -> bool {
        !self.payload.is_empty()
    }

    /// Returns the payload length as a u16, saturating if needed
    pub fn payload_len_u16(&self) -> u16 {
        self.payload.len().min(u16::MAX as usize) as u16
    }
}

impl fmt::Display for Frame {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "Frame {{ type: {}, seq: {}, payload_len: {} }}",
            self.frame_type,
            self.seq,
            self.payload.len()
        )
    }
}

/// Size of the fixed frame header in bytes:
/// 1 (type) + 4 (seq) + 2 (payload_len) = 7
pub const HEADER_SIZE: usize = 7;

/// Maximum allowed payload size (64 KiB - 1)
pub const MAX_PAYLOAD_SIZE: usize = (u16::MAX as usize);

/// Wire format offsets
pub mod offsets {
    pub const TYPE_OFFSET: usize = 0;
    pub const SEQ_OFFSET: usize = 1;
    pub const PAYLOAD_LEN_OFFSET: usize = 5;
    pub const PAYLOAD_OFFSET: usize = 7;
}

/// Frame validation errors
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum FrameError {
    /// Buffer is too short to contain a complete header
    HeaderTooShort { got: usize, need: usize },
    /// Payload length field exceeds maximum
    PayloadTooLarge { len: usize, max: usize },
    /// Buffer is too short to contain the declared payload
    PayloadTruncated { got: usize, need: usize },
    /// Zero-length payload handling triggered an unexpected path
    MultiByteLengthPrefix,
    /// Generic decode failure
    DecodeFailed(String),
    /// Generic encode failure
    EncodeFailed(String),
}

impl fmt::Display for FrameError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            FrameError::HeaderTooShort { got, need } =>
                write!(f, "header too short: got {} bytes, need {}", got, need),
            FrameError::PayloadTooLarge { len, max } =>
                write!(f, "payload too large: {} > max {}", len, max),
            FrameError::PayloadTruncated { got, need } =>
                write!(f, "payload truncated: got {} bytes, need {}", got, need),
            FrameError::MultiByteLengthPrefix =>
                write!(f, "multi-byte length prefix error"),
            FrameError::DecodeFailed(msg) =>
                write!(f, "decode failed: {}", msg),
            FrameError::EncodeFailed(msg) =>
                write!(f, "encode failed: {}", msg),
        }
    }
}

impl std::error::Error for FrameError {}
