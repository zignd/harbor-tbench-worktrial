import struct

def parse_bpack_file(filepath):
    records = []
    with open(filepath, "rb") as f:
        data = f.read()
    if len(data) < 16:
        return records
    magic, ver, count, base_ts = struct.unpack_from("<4sHHQ", data, 0)
    if magic != b"BPK1":
        return records
    offset = 16
    for i in range(count):
        if offset + 16 > len(data):
            break
        delta_start, dur, wid, exit_c, ep_len = struct.unpack_from("<IIIIH", data, offset)
        offset += 16
        ep = data[offset:offset+ep_len].decode("utf-8", errors="ignore")
        offset += ep_len
        records.append({
            "id": f"{filepath}:{i}",
            "start_ms": base_ts + delta_start,
            "duration_ms": dur,
            "t_end": base_ts + delta_start + dur,
            "worker_id": wid,
            "exit_code": exit_c,
            "endpoint": ep
        })
    return records
