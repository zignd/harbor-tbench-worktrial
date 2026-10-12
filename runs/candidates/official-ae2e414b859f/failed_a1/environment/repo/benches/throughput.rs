use criterion::{criterion_group, criterion_main, Criterion, BenchmarkId};
use packet_codec::{decode_packet, encode_packet};
use packet_codec::codec::Packet;
use rand::{Rng, SeedableRng};
use rand::rngs::StdRng;

fn bench_throughput(c: &mut Criterion) {
    let mut rng = StdRng::seed_from_u64(0xDEADBEEF);
    // Generate a corpus of 500 packets with varied lengths
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
