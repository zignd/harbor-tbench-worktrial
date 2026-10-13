import json
import time
import urllib.request
import urllib.error
import random

BASE_URL = 'http://127.0.0.1:9090'

def test_sample():
    print('[1] Checking daemon health...')
    try:
        req = urllib.request.Request(f'{BASE_URL}/healthz')
        with urllib.request.urlopen(req, timeout=3) as resp:
            print(f'Health status: {resp.status}, response: {resp.read().decode()}')
    except Exception as e:
        print(f'Daemon not reachable at {BASE_URL}: {e}')
        return

    print('[2] Registering sample stream...')
    reg_payload = json.dumps({
        'stream_id': 'sample-stream',
        'min_value': 1.0,
        'max_value': 1000.0,
        'max_relative_error': 0.05,
        'priority': 1
    }).encode()
    req = urllib.request.Request(f'{BASE_URL}/v1/streams/register', data=reg_payload, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            print(f'Register status: {resp.status}, response: {resp.read().decode()}')
    except urllib.error.HTTPError as e:
        print(f'Register failed: {e.code}, {e.read().decode()}')
        return

    print('[3] Ingesting 500 uniform values...')
    random.seed(42)
    samples = [random.uniform(10.0, 100.0) for _ in range(500)]
    ingest_payload = json.dumps({'stream_id': 'sample-stream', 'values': samples}).encode()
    req = urllib.request.Request(f'{BASE_URL}/v1/ingest', data=ingest_payload, headers={'Content-Type': 'application/json'})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=3) as resp:
        t_ingest = (time.perf_counter() - t0) * 1000
        print(f'Ingest took {t_ingest:.2f}ms')

    print('[4] Querying quantiles...')
    query_payload = json.dumps({'stream_id': 'sample-stream', 'quantiles': [0.5, 0.9, 0.99]}).encode()
    req = urllib.request.Request(f'{BASE_URL}/v1/query', data=query_payload, headers={'Content-Type': 'application/json'})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=3) as resp:
        t_query = (time.perf_counter() - t0) * 1000
        res = json.loads(resp.read().decode())
        print(f'Query took {t_query:.2f}ms, results: {res}')

if __name__ == '__main__':
    test_sample()
