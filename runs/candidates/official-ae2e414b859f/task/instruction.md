The `packet-codec` service in `/app/repo` is busted after the pipeline migration. It panics on some inputs and throughput dropped hard compared to the old branch.

Fix it so the codec roundtrips correctly for all inputs and the release build is properly optimized. The release profile must have `opt-level = 3` and `lto = true` set in `Cargo.toml`. Run `cargo test --release` in `/app/repo` to confirm all tests pass, and `cargo build --release` to produce the optimized binary.

The test suite in `/app/repo/tests/` is what we will run to verify your work.
