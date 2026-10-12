use packet_codec::{decode_packet, encode_packet};
use packet_codec::codec::Packet;

fn main() {
    let pkt = Packet::new(0x01, b"hello world".to_vec());
    let encoded = encode_packet(&pkt).expect("encode failed");
    let decoded = decode_packet(&encoded).expect("decode failed");
    assert_eq!(pkt, decoded);
    println!("packet-codec: roundtrip OK, {} bytes", encoded.len());
}
