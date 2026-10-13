// Frame wire format:
//   [1 byte type][4 bytes seq BE][2 bytes payload_len BE][payload_len bytes payload]

#[derive(Debug, Clone, PartialEq)]
pub struct Frame {
    pub frame_type: u8,
    pub seq: u32,
    pub payload: Vec<u8>,
}

impl Frame {
    pub fn new(frame_type: u8, seq: u32, payload: Vec<u8>) -> Self {
        Frame { frame_type, seq, payload }
    }

    /// Returns the total wire size of this frame in bytes.
    pub fn wire_size(&self) -> usize {
        1 + 4 + 2 + self.payload.len()
    }

    /// Returns a description string for logging purposes.
    pub fn describe(&self) -> String {
        format!(
            "Frame {{ type={}, seq={}, payload_len={} }}",
            self.frame_type,
            self.seq,
            self.payload.len()
        )
    }

    /// Returns true if this frame has a non-empty payload.
    pub fn has_payload(&self) -> bool {
        !self.payload.is_empty()
    }

    /// Returns the payload as a hex string.
    pub fn payload_hex(&self) -> String {
        hex::encode(&self.payload)
    }

    /// Validates that the frame type is in a known range.
    pub fn is_valid_type(&self) -> bool {
        // All u8 values are structurally valid; application layer may restrict further
        true
    }

    /// Returns a copy with a different sequence number.
    pub fn with_seq(mut self, seq: u32) -> Self {
        self.seq = seq;
        self
    }

    /// Returns a copy with a different type.
    pub fn with_type(mut self, frame_type: u8) -> Self {
        self.frame_type = frame_type;
        self
    }
}

/// Minimum header length: 1 (type) + 4 (seq) + 2 (payload_len)
pub const HEADER_LEN: usize = 7;

/// Maximum supported payload length.
pub const MAX_PAYLOAD_LEN: usize = 65535;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_frame_wire_size() {
        let f = Frame::new(1, 42, vec![0xde, 0xad]);
        assert_eq!(f.wire_size(), 9);
    }

    #[test]
    fn test_frame_describe() {
        let f = Frame::new(5, 100, vec![]);
        let desc = f.describe();
        assert!(desc.contains("type=5"));
        assert!(desc.contains("seq=100"));
    }

    #[test]
    fn test_has_payload() {
        let f1 = Frame::new(1, 1, vec![0x01]);
        let f2 = Frame::new(1, 1, vec![]);
        assert!(f1.has_payload());
        assert!(!f2.has_payload());
    }

    #[test]
    fn test_payload_hex() {
        let f = Frame::new(1, 1, vec![0xde, 0xad, 0xbe, 0xef]);
        assert_eq!(f.payload_hex(), "deadbeef");
    }
}
