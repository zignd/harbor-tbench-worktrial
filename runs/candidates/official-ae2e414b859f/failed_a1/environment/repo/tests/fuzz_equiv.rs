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

    // Ensure we test power-of-two lengths explicitly
    let mut pow2_lengths: Vec<usize> = (0..=10).map(|i| 1usize << i).collect(); // 1,2,4,...,1024
    // For each power-of-two length, generate 50 packets
    let mut test_cases: Vec<(usize, Vec<u8>)> = Vec::new();
    for &len in &pow2_lengths {
        for _ in 0..50 {
            let data: Vec<u8> = (0..len).map(|_| rng.gen::<u8>()).collect();
            test_cases.push((len, data));
        }
    }
    // Fill remaining with random-length packets
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
    // Specific regression: 127-byte payload must roundtrip correctly
    let data = vec![0xABu8; 127];
    let pkt = Packet::new(0x42, data);
    let encoded = encode_packet(&pkt).expect("encode failed");
    let decoded = decode_packet(&encoded).expect("decode failed on 127-byte payload");
    assert_eq!(pkt, decoded, "127-byte payload roundtrip failed");
}

#[test]
fn fuzz_power_of_two_lengths() {
    // Explicitly test all power-of-two lengths from 1 to 1024
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
