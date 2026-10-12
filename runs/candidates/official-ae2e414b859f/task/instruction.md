The `packet-codec` service in `/app/repo` is busted after the pipeline migration. It panics on some inputs and throughput dropped hard compared to the old branch. We need average encode+decode latency at or below 200 ns/packet on the fuzz corpus.

Check the history, figure out what broke, and fix it so the codec roundtrips correctly for all inputs and hits the performance bar. Run `cargo test --release` in `/app/repo` to confirm all tests pass. The benchmark uses the binary produced by `cargo build --release`.

The test suite in `/app/repo/tests/` and `/app/repo/benches/` is what we'll run to verify your work.
