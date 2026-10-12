.PHONY: all build test bench clean

all: build

build:
	cargo build --release

test:
	cargo test --release

bench:
	cargo bench --bench throughput 2>&1 | tee /tmp/bench_raw.txt

clean:
	cargo clean

check:
	cargo check
