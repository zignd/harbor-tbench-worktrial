#!/usr/bin/env python3
"""Small endpoint smoke run against the deployed service."""
import argparse
import json
import math
import random
import urllib.request


def post(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as res:
        return json.load(res)


def get(url):
    with urllib.request.urlopen(url, timeout=5) as res:
        return json.load(res)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:9090")
    parser.add_argument("--count", type=int, default=500)
    args = parser.parse_args()
    rng = random.Random(2025)
    values = [round(rng.uniform(1.0, 1000.0), 6) for _ in range(args.count)]
    exact = sorted(values)[math.ceil(0.99 * len(values)) - 1]
    register = post(args.url + "/v1/streams/register", {
        "budget": 2048,
        "streams": [{
            "name": "sample",
            "min_value": 0.5,
            "max_value": 2000.0,
            "priority": 100,
            "max_relative_error": 0.01,
        }],
    })
    ingest = post(args.url + "/v1/ingest", {
        "stream": "sample",
        "events": [{"latency_ms": value} for value in values],
    })
    query = post(args.url + "/v1/query", {
        "stream": "sample",
        "quantiles": [0.5, 0.9, 0.99],
    })
    error = abs(query["estimates"][-1] - exact) / exact
    print(json.dumps({
        "health": get(args.url + "/healthz"),
        "register": register,
        "ingest": ingest,
        "query": query,
        "p99_exact": exact,
        "p99_relative_error": error,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
