#!/bin/bash
set -e

REPO=/app/repo
rm -rf "$REPO"
mkdir -p "$REPO"
cd "$REPO"

git init -b main
git config user.email "platform@example.com"
git config user.name "Platform Team"

# Create directory structure
mkdir -p src tests benches

# ── Commit 1: initial skeleton ──────────────────────────────────────────────
cat > src/lib.rs <<'EOF'
// packet-codec library root
pub mod codec;
pub mod frame;
pub mod stats;
pub mod proto;
EOF

cp /app/environment/src_codec_rs src/codec.rs
cp /app/environment/src_frame_rs_good src/frame.rs
cp /app/environment/src_stats_rs src/stats.rs
cp /app/environment/src_proto_rs src/proto.rs
cp /app/environment/src_main_rs src/main.rs
cp /app/environment/Cargo_toml_good Cargo.toml
cp /app/environment/tests_fuzz_equiv_rs tests/fuzz_equiv.rs
cp /app/environment/benches_throughput_rs benches/throughput.rs
cp /app/environment/Makefile Makefile

cat > README.md <<'EOF'
# packet-codec

High-performance packet encoding and decoding library for the platform pipeline.

## Usage

```
cargo build --release
cargo test
```

## Architecture

- `src/codec.rs` — LEB128 varint codec and Packet type
- `src/frame.rs` — Frame delimiter logic (4-byte length prefix)
- `src/stats.rs` — Packet statistics and accounting
- `src/proto.rs` — Protocol constants and message types
EOF

git add -A
git commit -m "initial commit: packet-codec library skeleton"

# ── Commit 2: add stats module ───────────────────────────────────────────────
cat >> src/stats.rs <<'EOF'

// Extended statistics for pipeline monitoring
pub fn format_stats(stats: &PacketStats) -> String {
    format!(
        "PacketStats {{ encoded: {}, decoded: {}, bytes_in: {}, bytes_out: {}, errors: {} }}",
        stats.packets_encoded,
        stats.packets_decoded,
        stats.bytes_encoded,
        stats.bytes_decoded,
        stats.errors,
    )
}
EOF
git add -A
git commit -m "add stats formatting helper"

# ── Commit 3: add proto message routing ─────────────────────────────────────
cat >> src/proto.rs <<'EOF'

/// Route a message to the appropriate pipeline stage.
pub fn route_message(tag: u8) -> PipelineStage {
    match MessageType::from_tag(tag) {
        MessageType::Heartbeat => PipelineStage::Ingress,
        MessageType::DataPacket => PipelineStage::Processing,
        MessageType::Ack | MessageType::Nack => PipelineStage::Egress,
        MessageType::Control => PipelineStage::Routing,
        MessageType::Metrics => PipelineStage::Egress,
        MessageType::Unknown => PipelineStage::Ingress,
    }
}
EOF
git add -A
git commit -m "add message routing to proto module"

# ── Commit 4: performance tuning ─────────────────────────────────────────────
cat >> src/codec.rs <<'EOF'

/// Pre-compute encoded size without allocating.
pub fn encoded_size(payload_len: usize) -> usize {
    let mut n = payload_len as u64;
    let mut varint_bytes = 1usize;
    while n > 127 { n >>= 7; varint_bytes += 1; }
    1 + varint_bytes + payload_len
}
EOF
git add -A
git commit -m "add encoded_size helper for pre-allocation"

# ── Commit 5: tag this as old-pipeline release ───────────────────────────────
git tag v0.2.0
git branch old-pipeline

# ── Now create main branch with migration bugs ───────────────────────────────

# ── Commit 6: migrate build pipeline ─────────────────────────────────────────
cp /app/environment/Cargo_toml_buggy Cargo.toml
cp /app/environment/MIGRATION_NOTES_md MIGRATION_NOTES.md
git add -A
git commit -m "migrate build pipeline: update Cargo config for new CI"

# ── Commit 7: harden codec bounds checks ─────────────────────────────────────
# Touch codec.rs to make it look like it was modified
cat >> src/codec.rs <<'EOF'

// Safety: additional bounds validation added during pipeline migration review.
// See MIGRATION_NOTES.md for context.
#[inline(always)]
pub fn validate_payload_size(len: usize) -> bool {
    len <= crate::proto::MAX_PAYLOAD_SIZE
}
EOF
git add -A
git commit -m "harden codec bounds checks: add payload size validation"

# ── Commit 8: introduce frame.rs off-by-one ───────────────────────────────────
cp /app/environment/src_frame_rs_buggy src/frame.rs
git add -A
git commit -m "update Cargo config for new CI: align frame handling with migration spec"

git tag v0.3.0

echo "Repository setup complete."
git --no-pager log --oneline --all

# Pin dependencies for Rust 1.82 compatibility
cd /app/repo
cargo update clap --precise 4.5.0
