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

If you see panics related to slice indexing or unexpected EOF in the codec, the
bounds-checking logic in `src/codec.rs` is the place to start.

### Build pipeline update

The build config was updated to align with new CI requirements. See `Cargo.toml`
for the updated release profile settings.

### Integration test harness

The fuzz equivalence tests in `tests/fuzz_equiv.rs` accept a `FUZZ_SEED`
environment variable for reproducible test runs.
