/// Utility functions for the framecodec service.

/// Format a byte slice as a colon-separated hex string (e.g., "de:ad:be:ef").
pub fn format_hex_colon(bytes: &[u8]) -> String {
    bytes
        .iter()
        .map(|b| format!("{:02x}", b))
        .collect::<Vec<_>>()
        .join(":")
}

/// Format a byte slice as a spaced hex dump with optional ASCII sidebar.
pub fn hex_dump(bytes: &[u8], width: usize) -> String {
    let mut result = String::new();
    let col_width = width * 3;
    for (i, chunk) in bytes.chunks(width).enumerate() {
        let offset = i * width;
        let hex_part: String = chunk
            .iter()
            .map(|b| format!("{:02x} ", b))
            .collect();
        let ascii_part: String = chunk
            .iter()
            .map(|&b| if b.is_ascii_graphic() || b == b' ' { b as char } else { '.' })
            .collect();
        let padded = format!("{:<width$}", hex_part, width = col_width);
        result.push_str(&format!("{:08x}  {}  |{}|\n", offset, padded, ascii_part));
    }
    result
}

/// Parse a hex string into bytes, returning None on failure.
pub fn parse_hex(s: &str) -> Option<Vec<u8>> {
    hex::decode(s).ok()
}

/// Compute a simple 32-bit checksum (XOR fold) of a byte slice.
pub fn checksum32(data: &[u8]) -> u32 {
    let mut acc: u32 = 0;
    for chunk in data.chunks(4) {
        let mut word = [0u8; 4];
        word[..chunk.len()].copy_from_slice(chunk);
        acc ^= u32::from_le_bytes(word);
    }
    acc
}

/// Compute a simple 16-bit checksum (sum of bytes, wrapping) of a byte slice.
pub fn checksum16(data: &[u8]) -> u16 {
    data.iter().fold(0u16, |acc, &b| acc.wrapping_add(b as u16))
}

/// Escape non-printable bytes in a string for display.
pub fn escape_bytes(bytes: &[u8]) -> String {
    let mut s = String::new();
    for &b in bytes {
        if b.is_ascii_graphic() || b == b' ' {
            s.push(b as char);
        } else {
            s.push_str(&format!("\\x{:02x}", b));
        }
    }
    s
}

/// Truncate a byte slice to at most `max_len` bytes for display.
pub fn truncate_bytes(bytes: &[u8], max_len: usize) -> &[u8] {
    if bytes.len() > max_len {
        &bytes[..max_len]
    } else {
        bytes
    }
}

/// Returns true if the slice is all-zero bytes.
pub fn is_all_zeros(data: &[u8]) -> bool {
    data.iter().all(|&b| b == 0)
}

/// Pad a byte slice to the given length with zero bytes on the right.
pub fn zero_pad(data: &[u8], total_len: usize) -> Vec<u8> {
    let mut v = data.to_vec();
    if v.len() < total_len {
        v.resize(total_len, 0);
    }
    v
}

/// Split a byte slice into chunks of the given size.
pub fn chunk_bytes(data: &[u8], chunk_size: usize) -> Vec<&[u8]> {
    if chunk_size == 0 {
        return vec![];
    }
    data.chunks(chunk_size).collect()
}

/// Returns the index of the first differing byte between two slices, or None.
pub fn first_diff(a: &[u8], b: &[u8]) -> Option<usize> {
    let len = a.len().min(b.len());
    for i in 0..len {
        if a[i] != b[i] {
            return Some(i);
        }
    }
    if a.len() != b.len() {
        Some(len)
    } else {
        None
    }
}

/// Simple ring-buffer for storing the last N byte-slice events.
pub struct RingLog {
    capacity: usize,
    entries: std::collections::VecDeque<Vec<u8>>,
}

impl RingLog {
    pub fn new(capacity: usize) -> Self {
        RingLog {
            capacity,
            entries: std::collections::VecDeque::with_capacity(capacity),
        }
    }

    pub fn push(&mut self, entry: Vec<u8>) {
        if self.entries.len() == self.capacity {
            self.entries.pop_front();
        }
        self.entries.push_back(entry);
    }

    pub fn len(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    pub fn iter(&self) -> impl Iterator<Item = &Vec<u8>> {
        self.entries.iter()
    }

    pub fn get(&self, index: usize) -> Option<&Vec<u8>> {
        self.entries.get(index)
    }

    pub fn clear(&mut self) {
        self.entries.clear();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_format_hex_colon() {
        let result = format_hex_colon(&[0xde, 0xad, 0xbe, 0xef]);
        assert_eq!(result, "de:ad:be:ef");
    }

    #[test]
    fn test_parse_hex() {
        assert_eq!(parse_hex("deadbeef"), Some(vec![0xde, 0xad, 0xbe, 0xef]));
        assert_eq!(parse_hex("xyz"), None);
    }

    #[test]
    fn test_checksum32() {
        let data = [0x01, 0x02, 0x03, 0x04];
        let c = checksum32(&data);
        assert_eq!(c, 0x04030201);
    }

    #[test]
    fn test_checksum16() {
        let data = [0x01, 0x02, 0x03];
        let c = checksum16(&data);
        assert_eq!(c, 6);
    }

    #[test]
    fn test_is_all_zeros() {
        assert!(is_all_zeros(&[0, 0, 0]));
        assert!(!is_all_zeros(&[0, 1, 0]));
        assert!(is_all_zeros(&[]));
    }

    #[test]
    fn test_zero_pad() {
        let padded = zero_pad(&[1, 2], 5);
        assert_eq!(padded, vec![1, 2, 0, 0, 0]);
    }

    #[test]
    fn test_first_diff() {
        assert_eq!(first_diff(&[1, 2, 3], &[1, 2, 4]), Some(2));
        assert_eq!(first_diff(&[1, 2], &[1, 2]), None);
        assert_eq!(first_diff(&[1], &[1, 2]), Some(1));
    }

    #[test]
    fn test_ring_log() {
        let mut log = RingLog::new(3);
        log.push(vec![1]);
        log.push(vec![2]);
        log.push(vec![3]);
        log.push(vec![4]);
        assert_eq!(log.len(), 3);
        assert_eq!(log.get(0), Some(&vec![2]));
    }

    #[test]
    fn test_escape_bytes() {
        let s = escape_bytes(&[0x41, 0x00, 0x42]);
        assert_eq!(s, "A\\x00B");
    }

    #[test]
    fn test_hex_dump_nonempty() {
        let dump = hex_dump(&[0xde, 0xad], 16);
        assert!(dump.contains("de ad"));
    }
}
