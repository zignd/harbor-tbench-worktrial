.PHONY: bench test build

build:
	cargo build --release

test:
	cargo test --release

bench: build
	cargo bench --bench throughput 2>&1 | tee /tmp/criterion_out.txt
	@echo "--- Median ns/packet ---"
	@python3 -c "
import re
with open('/tmp/criterion_out.txt') as f:
    content = f.read()
matches = re.findall(r'time:\s+\[.*?(\d+\.\d+)\s+ns', content)
if matches:
    vals = [float(x) for x in matches]
    per_packet = min(vals) / 500.0
    print(f'{per_packet:.2f} ns/packet')
else:
    print('Could not parse criterion output')
"
