The NetFlow v9 aggregation service at `/app` starts correctly but returns empty or incorrect flow data when queried after traffic is replayed into it.

Repair the service so that:

1. After UDP NetFlow v9 records are replayed to port 9995, TCP queries on port 9996 return accurate aggregated flow data. The service is started with `cargo run -- --udp 9995 --tcp 9996` from `/app` and queries are issued as newline-terminated JSON objects over a TCP connection.

2. Each query response is a JSON object with a `flows` array; each element has `src_ip`, `dst_ip`, `proto`, `packets`, and `bytes` fields with correct values.

3. The `top_talkers` query (with a `limit` integer field) returns flows sorted descending by `bytes`, limited to the requested count.

4. The `by_proto` query (with a `proto` integer field) returns all flows matching that IP protocol number, sorted descending by `bytes`.

5. The `src_filter` query (with a `src_prefix` field in CIDR notation such as `"10.1.0.0/24"`) returns all flows whose source IP falls within that prefix, sorted descending by `bytes`.

6. Multiple flow records arriving with the same `(src_ip, dst_ip, proto)` key — whether in the same datagram or across separate datagrams — must have their `packets` and `bytes` summed into a single aggregated entry.

7. Data records that arrive before their corresponding template record has been received must still be processed once the template arrives; no flow records may be silently discarded because of template ordering.

The source is in `/app/src/`. Captured test traffic is in `/app/captures/`. A replay tool is at `/app/tools/replay_capture.py` and a capture generator is at `/app/tools/gen_capture.py`.
