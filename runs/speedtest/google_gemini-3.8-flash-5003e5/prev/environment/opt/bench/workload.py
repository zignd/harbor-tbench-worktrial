import json
import random
import sys
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:9090"

def post_json(path, data):
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def main():
    stream_id = "sample_stream"
    print("Registering sample stream...")
    reg_payload = {
        "stream_id": stream_id,
        "x_min": 1.0,
        "x_max": 1000.0,
        "alpha": 0.01,
        "max_alpha": 0.05,
        "priority": 1,
    }
    try:
        post_json("/v1/streams/register", reg_payload)
    except urllib.error.HTTPError as e:
        print(f"Stream registration returned: {e.code} {e.read().decode()}")

    print("Generating 500 sample latencies (uniform distribution)...")
    rng = random.Random(42)
    samples = [rng.uniform(10.0, 100.0) for _ in range(500)]

    print("Ingesting samples...")
    post_json("/v1/ingest", {"stream_id": stream_id, "values": samples})

    print("Querying percentiles...")
    res = post_json("/v1/query", {"stream_id": stream_id, "quantiles": [0.5, 0.9, 0.99]})
    print("Results:", res)
    print("Sample benchmark completed successfully.")

if __name__ == "__main__":
    main()
