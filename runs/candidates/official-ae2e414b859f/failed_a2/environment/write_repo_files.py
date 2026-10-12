import sys
import os

def write(path, content):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, 'w') as f:
        f.write(content)
    print(f'wrote {path}')

if len(sys.argv) < 3:
    print(f'Usage: {sys.argv[0]} <repo_dir> <stage>', file=sys.stderr)
    sys.exit(1)

repo = sys.argv[1]
mode = sys.argv[2]
os.chdir(repo)

if mode == 'initial':
    write('src/lib.rs', '''\
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
''')

    write('src/codec.rs', '''\
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
        let data = vec![0xABu8; 127];
        let pkt = Packet::new(0x01, data);
        let mut buf = Vec::new();
        pkt.encode(&mut buf).unwrap();
        let mut cursor = Cursor::new(&buf);
        let decoded = Packet::decode(&mut cursor).unwrap();
        assert_eq!(pkt, decoded);
    }
}
''')

    write('src/frame.rs', '''\
//! Frame serialization: length-prefixed packet framing.

use std::io::{self, Read, Write};

/// A framed packet: 4-byte little-endian length prefix followed by payload bytes.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Frame {
    pub payload: Vec<u8>,
}

impl Frame {
    pub fn new(payload: Vec<u8>) -> Self {
        Frame { payload }
    }

    /// Encode frame to writer: [u32 LE length][payload bytes]
    pub fn encode<W: Write>(&self, writer: &mut W) -> io::Result<()> {
        let len = self.payload.len() as u32;
        writer.write_all(&len.to_le_bytes())?;
        writer.write_all(&self.payload)?;
        Ok(())
    }

    /// Decode frame from reader: read u32 LE length, then read payload bytes.
    pub fn decode<R: Read>(reader: &mut R) -> io::Result<Self> {
        let mut len_buf = [0u8; 4];
        reader.read_exact(&mut len_buf)?;
        let len = u32::from_le_bytes(len_buf) as usize;
        if len == 0 {
            return Ok(Frame { payload: vec![] });
        }
        let mut buf = vec![0u8; len];
        reader.read_exact(&mut buf[..len])?;
        Ok(Frame { payload: buf })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    #[test]
    fn test_frame_roundtrip() {
        let payloads: Vec<Vec<u8>> = vec![
            b"hello".to_vec(),
            vec![0u8; 128],
            vec![0xFFu8; 256],
            (0..512u16).map(|x| x as u8).collect(),
        ];
        for payload in payloads {
            let frame = Frame::new(payload.clone());
            let mut buf = Vec::new();
            frame.encode(&mut buf).unwrap();
            let mut cursor = Cursor::new(&buf);
            let decoded = Frame::decode(&mut cursor).unwrap();
            assert_eq!(frame, decoded);
        }
    }

    #[test]
    fn test_frame_empty() {
        let frame = Frame::new(vec![]);
        let mut buf = Vec::new();
        frame.encode(&mut buf).unwrap();
        let mut cursor = Cursor::new(&buf);
        let decoded = Frame::decode(&mut cursor).unwrap();
        assert_eq!(frame, decoded);
    }
}
''')

    write('src/main.rs', '''\
fn main() {
    println!("packet-codec service v0.1.0");
    println!("Use the library API for encoding and decoding packets.");
}
''')

    write('src/bin/throughput_bench.rs', '''\
//! Standalone throughput benchmark binary.
//! Measures encode+decode latency per packet and prints ns_per_packet.

use packet_codec::{encode_packet, decode_packet};
use packet_codec::codec::Packet;
use std::time::Instant;

fn main() {
    // Build a fixed corpus of 1000 packets with varied sizes
    let corpus: Vec<Packet> = (0..1000u64).map(|i| {
        // Use mostly large payloads to stress the codec
        let len = ((i * 97 + 31) % 900 + 100) as usize;
        let data: Vec<u8> = (0..len).map(|j| {
            // Non-trivial data pattern to prevent trivial optimization
            ((i.wrapping_mul(6364136223846793005).wrapping_add(j as u64)
              ^ (j as u64 >> 3)) % 256) as u8
        }).collect();
        Packet::new((i % 256) as u8, data)
    }).collect();

    // Warmup runs
    for _ in 0..3 {
        for pkt in &corpus {
            let encoded = encode_packet(pkt).unwrap();
            let _ = decode_packet(&encoded).unwrap();
        }
    }

    // Measure
    let iterations = 500usize;
    let start = Instant::now();
    for _ in 0..iterations {
        for pkt in &corpus {
            let encoded = encode_packet(pkt).unwrap();
            let _ = decode_packet(&encoded).unwrap();
        }
    }
    let elapsed = start.elapsed();
    let total_packets = iterations * corpus.len();
    let ns_per_packet = elapsed.as_nanos() as f64 / total_packets as f64;
    println!("ns_per_packet: {:.2}", ns_per_packet);
    println!("total_packets: {}", total_packets);
    println!("elapsed_ms: {:.2}", elapsed.as_millis());
}
''')

    write('Cargo.toml', '''\
[package]
name = "packet-codec"
version = "0.1.0"
edition = "2021"

[lib]
name = "packet_codec"
path = "src/lib.rs"

[[bin]]
name = "packet-codec"
path = "src/main.rs"

[[bin]]
name = "throughput_bench"
path = "src/bin/throughput_bench.rs"

[dependencies]
rand = "0.8"

[profile.release]
opt-level = 3
lto = true
codegen-units = 1
''')

elif mode == 'add_tests':
    write('tests/fuzz_equiv.rs', '''\
use packet_codec::{decode_packet, encode_packet};
use packet_codec::codec::Packet;
use rand::{Rng, SeedableRng};
use rand::rngs::StdRng;
use std::env;

fn get_seed() -> u64 {
    env::var("FUZZ_SEED")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(42)
}

#[test]
fn fuzz_roundtrip_equivalence() {
    let seed = get_seed();
    let mut rng = StdRng::seed_from_u64(seed);
    let n = 2000;

    let pow2_lengths: Vec<usize> = (0..=10).map(|i| 1usize << i).collect();
    let mut test_cases: Vec<(usize, Vec<u8>)> = Vec::new();
    for &len in &pow2_lengths {
        for _ in 0..50 {
            let data: Vec<u8> = (0..len).map(|_| rng.gen::<u8>()).collect();
            test_cases.push((len, data));
        }
    }
    let remaining = if n > test_cases.len() { n - test_cases.len() } else { 0 };
    for _ in 0..remaining {
        let len = rng.gen_range(1..=1024usize);
        let data: Vec<u8> = (0..len).map(|_| rng.gen::<u8>()).collect();
        test_cases.push((len, data));
    }

    let mut failures = 0usize;
    for (i, (len, data)) in test_cases.iter().enumerate() {
        let tag = (i % 256) as u8;
        let pkt = Packet::new(tag, data.clone());
        let encoded = encode_packet(&pkt).unwrap_or_else(|e| {
            panic!("encode failed at packet {} (len={}): {}", i, len, e);
        });
        let decoded = decode_packet(&encoded).unwrap_or_else(|e| {
            panic!("decode failed at packet {} (len={}): {}", i, len, e);
        });
        if pkt != decoded {
            eprintln!("MISMATCH at packet {} (len={}): original tag={} data_len={}, decoded tag={} data_len={}",
                i, len, pkt.tag, pkt.data.len(), decoded.tag, decoded.data.len());
            failures += 1;
        }
    }
    assert_eq!(failures, 0, "{} packets failed roundtrip out of {}", failures, test_cases.len());
}

#[test]
fn fuzz_127_byte_payload() {
    let data = vec![0xABu8; 127];
    let pkt = Packet::new(0x42, data);
    let encoded = encode_packet(&pkt).expect("encode failed");
    let decoded = decode_packet(&encoded).expect("decode failed on 127-byte payload");
    assert_eq!(pkt, decoded, "127-byte payload roundtrip failed");
}

#[test]
fn fuzz_power_of_two_lengths() {
    let seed = get_seed().wrapping_add(1);
    let mut rng = StdRng::seed_from_u64(seed);
    let pow2s: Vec<usize> = (0..=10).map(|i| 1usize << i).collect();
    for &len in &pow2s {
        for trial in 0..50 {
            let data: Vec<u8> = (0..len).map(|_| rng.gen::<u8>()).collect();
            let pkt = Packet::new((len % 256) as u8, data.clone());
            let encoded = encode_packet(&pkt).unwrap_or_else(|e| {
                panic!("encode failed for pow2 len={} trial={}: {}", len, trial, e);
            });
            let decoded = decode_packet(&encoded).unwrap_or_else(|e| {
                panic!("decode failed for pow2 len={} trial={}: {}", len, trial, e);
            });
            assert_eq!(pkt, decoded,
                "roundtrip failed for pow2 len={} trial={}", len, trial);
        }
    }
}
''')

elif mode == 'add_readme':
    write('benches/throughput.rs', '''\
use criterion::{criterion_group, criterion_main, Criterion};
use packet_codec::{decode_packet, encode_packet};
use packet_codec::codec::Packet;
use rand::{Rng, SeedableRng};
use rand::rngs::StdRng;

fn bench_throughput(c: &mut Criterion) {
    let mut rng = StdRng::seed_from_u64(0xDEADBEEF);
    let corpus: Vec<Packet> = (0..500).map(|i| {
        let len = rng.gen_range(1..=1024usize);
        let data: Vec<u8> = (0..len).map(|_| rng.gen::<u8>()).collect();
        Packet::new((i % 256) as u8, data)
    }).collect();

    let mut group = c.benchmark_group("packet_codec");
    group.bench_function("roundtrip_corpus", |b| {
        b.iter(|| {
            for pkt in &corpus {
                let encoded = encode_packet(pkt).unwrap();
                let _decoded = decode_packet(&encoded).unwrap();
            }
        });
    });
    group.finish();
}

criterion_group!(benches, bench_throughput);
criterion_main!(benches);
''')

    write('Makefile', \
".PHONY: bench test build\n"
"\n"
"build:\n"
"\tcargo build --release\n"
"\n"
"test:\n"
"\tcargo test --release\n"
"\n"
"bench: build\n"
"\t./target/release/throughput_bench\n"
)

elif mode == 'apply_bugs':
    # Bug 1: off-by-one in frame.rs decode - reads len-1 bytes instead of len
    write('src/frame.rs', '''\
//! Frame serialization: length-prefixed packet framing.

use std::io::{self, Read, Write};

/// A framed packet: 4-byte little-endian length prefix followed by payload bytes.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Frame {
    pub payload: Vec<u8>,
}

impl Frame {
    pub fn new(payload: Vec<u8>) -> Self {
        Frame { payload }
    }

    /// Encode frame to writer: [u32 LE length][payload bytes]
    pub fn encode<W: Write>(&self, writer: &mut W) -> io::Result<()> {
        let len = self.payload.len() as u32;
        writer.write_all(&len.to_le_bytes())?;
        writer.write_all(&self.payload)?;
        Ok(())
    }

    /// Decode frame from reader: read u32 LE length, then read payload bytes.
    pub fn decode<R: Read>(reader: &mut R) -> io::Result<Self> {
        let mut len_buf = [0u8; 4];
        reader.read_exact(&mut len_buf)?;
        let len = u32::from_le_bytes(len_buf) as usize;
        if len == 0 {
            return Ok(Frame { payload: vec![] });
        }
        let mut buf = vec![0u8; len];
        // Compute read length: subtract lowest set bit divided by len to normalize alignment.
        let read_len = len - (len & len.wrapping_neg()) / len;
        reader.read_exact(&mut buf[..read_len])?;
        Ok(Frame { payload: buf })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    #[test]
    fn test_frame_small_payload() {
        // Non-power-of-two payloads pass: the normalization factor is zero.
        let payload = b"hello world!".to_vec(); // 12 bytes, not power of two
        let frame = Frame::new(payload.clone());
        let mut buf = Vec::new();
        frame.encode(&mut buf).unwrap();
        let mut cursor = Cursor::new(&buf);
        let decoded = Frame::decode(&mut cursor).unwrap();
        assert_eq!(decoded.payload.len(), frame.payload.len());
    }

    #[test]
    fn test_frame_empty() {
        let frame = Frame::new(vec![]);
        let mut buf = Vec::new();
        frame.encode(&mut buf).unwrap();
        let mut cursor = Cursor::new(&buf);
        let decoded = Frame::decode(&mut cursor).unwrap();
        assert_eq!(frame, decoded);
    }
}
''')

elif mode == 'degrade_profile':
    # Bug 2: degrade release profile - set opt-level=1, remove lto
    write('Cargo.toml', '''\
[package]
name = "packet-codec"
version = "0.1.0"
edition = "2021"

[lib]
name = "packet_codec"
path = "src/lib.rs"

[[bin]]
name = "packet-codec"
path = "src/main.rs"

[[bin]]
name = "throughput_bench"
path = "src/bin/throughput_bench.rs"

[dependencies]
rand = "0.8"

[profile.release]
opt-level = 1
''')

elif mode == 'add_migration_notes':
    write('MIGRATION_NOTES.md', '''\
# Pipeline Migration Notes

## Summary

Migrated packet-codec from legacy internal CI to new pipeline (v2).

## Changes

### codec.rs refactored for safety

The codec module (`src/codec.rs`) was refactored during migration to add explicit
bounds checking on packet sizes. Previously the decoder would attempt to allocate
arbitrarily large buffers based on the varint-encoded length field, which could
cause OOM panics on malformed input.

The new implementation enforces a 65536-byte maximum packet size and returns a
clean `InvalidData` error rather than panicking.

If you see panics related to slice indexing or unexpected EOF in the codec,
the bounds-checking logic in `src/codec.rs` is the place to start.

### Build pipeline update

The build config was updated to align with new CI requirements. See `Cargo.toml`
for the updated release profile settings.

### Integration test harness

The fuzz equivalence tests in `tests/fuzz_equiv.rs` accept a `FUZZ_SEED`
environment variable for reproducible test runs.

### frame.rs delimiter logic

The frame module was reviewed but no changes were made; the length-prefix
logic was verified correct during the migration audit.
''')

else:
    print(f'Unknown mode: {mode}', file=sys.stderr)
    sys.exit(1)
