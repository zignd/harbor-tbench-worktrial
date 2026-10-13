The `packet-codec` service in `/app/repo` is broken after a pipeline migration. It panics on certain inputs and throughput has dropped significantly compared to the old branch.

The git history has both the old working branch (`old-pipeline`) and the current broken `main`. Figure out what changed and fix it so all of the following hold:

- `cargo test --release` in `/app/repo` passes every test for any random seed, including the `fuzz_127_byte_payload` regression test and the `fuzz_codec_roundtrip` suite.
- Every packet roundtrips byte-for-byte correctly (encode then decode returns the original value) for all payload lengths, including lengths that are exact powers of two.
- The `[profile.release]` section in `/app/repo/Cargo.toml` has `opt-level = 3` and `lto = true`.
- The criterion benchmark in `/app/repo/benches/throughput.rs` builds and runs successfully with `cargo bench`.

Your fix must be applied to the working tree so that `cargo test --release` in `/app/repo` passes all tests.
