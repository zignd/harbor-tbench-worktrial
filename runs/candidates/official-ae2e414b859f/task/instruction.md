The `packet-codec` service in `/app/repo` is broken after a pipeline migration. It panics on certain inputs and throughput has dropped significantly compared to the old branch. We need it passing all correctness tests and running at or below 200 ns average per packet on the fuzz corpus.

The test suite lives in `/app/repo/tests/` and the benchmark in `/app/repo/benches/`. Verification runs `cargo test --release` in `/app/repo` and measures median ns/packet from the criterion benchmark built with `cargo build --release`. Both must pass: every packet must roundtrip byte-for-byte correctly (encode then decode returns the original value), and the median encode+decode latency per packet must be at or below 200 ns.

The git history in `/app/repo` has both the old working branch (`old-pipeline`) and the current broken `master` branch. Your fix must be applied to the working tree (or committed) so that `cargo test --release` in `/app/repo` passes all tests with the corrected release profile.
