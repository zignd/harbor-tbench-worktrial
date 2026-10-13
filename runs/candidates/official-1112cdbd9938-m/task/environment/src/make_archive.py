import json, os
os.makedirs('/work/input', exist_ok=True)
with open('/work/input/archive.jsonl', 'w', encoding='utf-8') as out:
    for i in range(18000):
        row = {'event_id': f'base-{i}', 'revision': 1,
               'timestamp': f'2024-01-{i % 28 + 1:02d}T12:00:00Z',
               'actor': f'actor-{i % 31}', 'source': f'192.0.2.{i % 250 + 1}',
               'destination': f'2001:db8::{i + 1:x}', 'signature': 'valid'}
        out.write(json.dumps(row, ensure_ascii=False) + '\n')
with open('/work/input/manifest.json', 'w', encoding='utf-8') as out:
    json.dump({'chunks': ['archive.jsonl']}, out)
