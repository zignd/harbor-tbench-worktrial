The NetFlow v9 aggregation service at `/app` starts correctly but returns wrong results when queried after traffic is replayed.

The service binary is at `/usr/local/bin/netflow-aggregator`. Start it with `netflow-aggregator --udp 9995 --tcp 9996`. It listens on UDP port 9995 for NetFlow v9 datagrams and answers JSON queries on TCP port 9996. Source code is in `/app/src/`. A replay tool is at `/app/tools/replay_capture.py` and a capture generator at `/app/tools/gen_capture.py`. Sample captures are in `/app/captures/`.

Repair the service so that:

1. After UDP flow records are replayed into port 9995, TCP queries on port 9996 return accurate aggregated flow data matching the traffic. Each entry in the `flows` array contains `src_ip`, `dst_ip`, `proto`, `packets`, and `bytes` fields with correct values.
2. The `top_talkers` query returns flows sorted descending by `bytes`, limited to the count specified in the `limit` field.
3. The `by_proto` query accepts a `proto` field (integer) and returns all flows matching that protocol number, sorted descending by `bytes`.
4. The `src_filter` query accepts a `src_prefix` field in CIDR notation and returns all flows whose source IP falls within that prefix, sorted descending by `bytes`.
5. Multiple flow records sharing the same (src_ip, dst_ip, proto) key must have their `packets` and `bytes` summed together across all received UDP datagrams.
6. Flow data records received before their corresponding template record has been seen must be buffered and processed once the template arrives.

The verifier replays fresh traffic captures and issues all three query types. Rebuild the binary after editing source with `cargo build --release` in `/app` and copy it to `/usr/local/bin/netflow-aggregator`, or use `cargo run --release -- --udp 9995 --tcp 9996` directly.
