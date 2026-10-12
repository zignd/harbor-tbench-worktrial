// util.rs - Utility helpers for the framecodec service
use std::fmt::Write;

/// Format a byte slice as a lowercase hex string.
pub fn bytes_to_hex(bytes: &[u8]) -> String {
    let mut out = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        write!(out, "{:02x}", b).unwrap();
    }
    out
}

/// Parse a lowercase or uppercase hex string into bytes.
/// Returns None if the string has odd length or contains non-hex chars.
pub fn hex_to_bytes(s: &str) -> Option<Vec<u8>> {
    if s.len() % 2 != 0 {
        return None;
    }
    let mut out = Vec::with_capacity(s.len() / 2);
    let mut chars = s.chars();
    while let (Some(hi), Some(lo)) = (chars.next(), chars.next()) {
        let h = hi.to_digit(16)?;
        let l = lo.to_digit(16)?;
        out.push((h * 16 + l) as u8);
    }
    Some(out)
}

/// Truncate or pad a byte slice to exactly `len` bytes.
/// If the slice is shorter, it is padded with zeros on the right.
/// If longer, it is truncated.
pub fn fit_bytes(bytes: &[u8], len: usize) -> Vec<u8> {
    let mut out = vec![0u8; len];
    let copy_len = bytes.len().min(len);
    out[..copy_len].copy_from_slice(&bytes[..copy_len]);
    out
}

/// Return a human-readable description of a byte count.
pub fn human_bytes(n: usize) -> String {
    if n < 1024 {
        format!("{} B", n)
    } else if n < 1024 * 1024 {
        format!("{:.1} KiB", n as f64 / 1024.0)
    } else {
        format!("{:.1} MiB", n as f64 / (1024.0 * 1024.0))
    }
}

/// XOR two byte slices of equal length, returning a new Vec.
/// Returns None if lengths differ.
pub fn xor_bytes(a: &[u8], b: &[u8]) -> Option<Vec<u8>> {
    if a.len() != b.len() {
        return None;
    }
    Some(a.iter().zip(b.iter()).map(|(x, y)| x ^ y).collect())
}

/// Simple checksum: sum all bytes mod 256.
pub fn checksum_u8(data: &[u8]) -> u8 {
    data.iter().fold(0u8, |acc, &b| acc.wrapping_add(b))
}

/// Compute a 32-bit FNV-1a hash of the given bytes.
pub fn fnv1a_32(data: &[u8]) -> u32 {
    const OFFSET_BASIS: u32 = 2166136261;
    const PRIME: u32 = 16777619;
    data.iter().fold(OFFSET_BASIS, |hash, &b| {
        (hash ^ b as u32).wrapping_mul(PRIME)
    })
}

/// Encode a u32 as big-endian bytes.
pub fn u32_to_be(n: u32) -> [u8; 4] {
    n.to_be_bytes()
}

/// Decode a big-endian u32 from a 4-byte slice.
pub fn u32_from_be(bytes: [u8; 4]) -> u32 {
    u32::from_be_bytes(bytes)
}

/// Encode a u16 as big-endian bytes.
pub fn u16_to_be(n: u16) -> [u8; 2] {
    n.to_be_bytes()
}

/// Decode a big-endian u16 from a 2-byte slice.
pub fn u16_from_be(bytes: [u8; 2]) -> u16 {
    u16::from_be_bytes(bytes)
}

/// Split a buffer into chunks of at most `chunk_size` bytes.
pub fn chunk_bytes(data: &[u8], chunk_size: usize) -> Vec<&[u8]> {
    if chunk_size == 0 {
        return Vec::new();
    }
    data.chunks(chunk_size).collect()
}

/// Return true if the given string contains only ASCII printable characters.
pub fn is_ascii_printable(s: &str) -> bool {
    s.bytes().all(|b| b >= 0x20 && b < 0x7f)
}

/// Escape non-printable bytes in a slice as \xNN sequences.
pub fn escape_bytes(data: &[u8]) -> String {
    let mut out = String::new();
    for &b in data {
        if b >= 0x20 && b < 0x7f {
            out.push(b as char);
        } else {
            write!(out, "\\x{:02x}", b).unwrap();
        }
    }
    out
}

/// Clamp a usize value between min and max (inclusive).
pub fn clamp_usize(val: usize, min: usize, max: usize) -> usize {
    val.max(min).min(max)
}

/// Convert a slice of bytes to a Vec<u8> reversed.
pub fn reverse_bytes(data: &[u8]) -> Vec<u8> {
    data.iter().rev().cloned().collect()
}

/// Zero-pad a hex string to an even number of characters.
pub fn normalize_hex(s: &str) -> String {
    if s.len() % 2 == 0 {
        s.to_lowercase()
    } else {
        format!("0{}", s.to_lowercase())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_bytes_to_hex() {
        assert_eq!(bytes_to_hex(&[0xde, 0xad, 0xbe, 0xef]), "deadbeef");
        assert_eq!(bytes_to_hex(&[]), "");
    }

    #[test]
    fn test_hex_to_bytes() {
        assert_eq!(hex_to_bytes("deadbeef"), Some(vec![0xde, 0xad, 0xbe, 0xef]));
        assert_eq!(hex_to_bytes(""), Some(vec![]));
        assert_eq!(hex_to_bytes("gg"), None);
        assert_eq!(hex_to_bytes("abc"), None);
    }

    #[test]
    fn test_fit_bytes() {
        assert_eq!(fit_bytes(&[1, 2, 3], 5), vec![1, 2, 3, 0, 0]);
        assert_eq!(fit_bytes(&[1, 2, 3, 4, 5], 3), vec![1, 2, 3]);
    }

    #[test]
    fn test_checksum() {
        assert_eq!(checksum_u8(&[1, 2, 3]), 6);
        assert_eq!(checksum_u8(&[255, 1]), 0);
    }

    #[test]
    fn test_fnv1a() {
        // Just check it doesn't panic and returns something
        let h = fnv1a_32(b"hello");
        assert_ne!(h, 0);
    }

    #[test]
    fn test_xor_bytes() {
        assert_eq!(xor_bytes(&[0xff, 0x00], &[0x0f, 0xf0]), Some(vec![0xf0, 0xf0]));
        assert_eq!(xor_bytes(&[1], &[1, 2]), None);
    }
}
