#!/usr/bin/env python3
import json, os, sys, tempfile
from pathlib import Path

ROOT = Path('/opt/metricq')
STATE = ROOT / 'state'
JOURNAL = STATE / 'journal.ndjson'
CHECKPOINT = STATE / 'checkpoint.json'
LOG = ROOT / 'logs' / 'service.log'
BUGGY = True


def dump(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False)


def atomic(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=str(path.parent), prefix='.tmp-')
    with os.fdopen(fd, 'w') as f:
        f.write(dump(obj) + '\n')
        f.flush(); os.fsync(f.fileno())
    os.replace(name, path)


class Engine:
    def __init__(self):
        self.lateness = 10
        self.events = {}
        self.ids = {}
        self.max_ts = {}
        self.offset = 0
        self.recovered = 0
        STATE.mkdir(parents=True, exist_ok=True)
        (ROOT / 'logs').mkdir(parents=True, exist_ok=True)

    def clear(self):
        self.events = {}; self.ids = {}; self.max_ts = {}; self.offset = 0
        for p in (JOURNAL, CHECKPOINT):
            try: p.unlink()
            except FileNotFoundError: pass
        self.log('reset')

    def log(self, event, **kw):
        try:
            with LOG.open('a') as f: f.write(dump({'event': event, **kw}) + '\n')
        except OSError: pass

    def append(self, rec):
        STATE.mkdir(parents=True, exist_ok=True)
        with JOURNAL.open('a') as f:
            f.write(dump(rec) + '\n'); f.flush(); os.fsync(f.fileno())
        self.offset = JOURNAL.stat().st_size

    def apply(self, rec, from_replay=False):
        s, eid = rec['stream'], rec['event_id']
        key = (s, eid)
        if BUGGY:
            try:
                n = int(eid)
                if n <= self.max_ts.get(s, -1): return False
                self.max_ts[s] = n
            except Exception: pass
        else:
            if eid in self.ids.get(s, set()): return False
        ts = rec['timestamp']
        if s in self.max_ts and not BUGGY:
            cutoff = self.max_ts[s] - self.lateness
            if ts < cutoff: return False
        self.ids.setdefault(s, set()).add(eid)
        self.events.setdefault(s, []).append(rec)
        self.max_ts[s] = max(self.max_ts.get(s, ts), ts)
        return True

    def valid_event(self, x):
        return (isinstance(x, dict) and isinstance(x.get('stream'), str)
                and isinstance(x.get('event_id'), str)
                and isinstance(x.get('timestamp'), (int, float))
                and isinstance(x.get('value'), (int, float))
                and not isinstance(x.get('value'), bool)
                and x.get('weight', 1) > 0)

    def ingest(self, x):
        if not self.valid_event(x): return {'ok': False, 'error': 'invalid_request'}
        r = {'stream': x['stream'], 'event_id': x['event_id'], 'timestamp': x['timestamp'],
             'value': x['value'], 'weight': x.get('weight', 1)}
        key = (r['stream'], r['event_id'])
        if r['event_id'] in self.ids.get(r['stream'], set()):
            return {'ok': True, 'accepted': False, 'duplicate': True}
        if not BUGGY and r['stream'] in self.max_ts and r['timestamp'] < self.max_ts[r['stream']] - self.lateness:
            self.append(r); return {'ok': True, 'accepted': False, 'duplicate': False}
        self.append(r); accepted = self.apply(r)
        return {'ok': True, 'accepted': bool(accepted), 'duplicate': False}

    def checkpoint(self):
        snap = {'lateness': self.lateness, 'events': self.events, 'ids': {s: sorted(v) for s,v in self.ids.items()}, 'max_ts': self.max_ts, 'offset': self.offset}
        atomic(CHECKPOINT, snap)
        return {'ok': True, 'offset': self.offset}

    def recover(self):
        self.events = {}; self.ids = {}; self.max_ts = {}; self.offset = 0; self.recovered = 0
        start = 0
        if CHECKPOINT.exists():
            try:
                s = json.loads(CHECKPOINT.read_text())
                self.lateness = s.get('lateness', 10); self.events = s.get('events', {})
                self.ids = {k: set(v) for k,v in s.get('ids', {}).items()}; self.max_ts = s.get('max_ts', {})
                start = int(s.get('offset', 0)); self.offset = start
            except Exception: start = 0; self.events = {}; self.ids = {}; self.max_ts = {}
        if JOURNAL.exists():
            data = JOURNAL.read_bytes()
            valid_end = data.rfind(b'\n') + 1
            if valid_end < len(data):
                with JOURNAL.open('r+b') as jf:
                    jf.truncate(valid_end)
                data = data[:valid_end]
            pos = min(start, len(data))
            while pos < len(data):
                end = data.find(b'\n', pos)
                if end < 0: break
                line = data[pos:end]; pos = end + 1
                try: r = json.loads(line); 
                except Exception: continue
                if self.valid_event(r):
                    if self.apply(r, True): self.recovered += 1
            self.offset = len(data)
        self.log('recover', recovered=self.recovered, offset=self.offset)
        return {'ok': True, 'recovered': self.recovered, 'offset': self.offset}

    def query(self, x):
        if not (isinstance(x.get('stream'), str) and isinstance(x.get('start'), (int,float)) and isinstance(x.get('end'), (int,float)) and isinstance(x.get('quantile'), (int,float)) and 0 <= x['quantile'] <= 1):
            return {'ok': False, 'error': 'invalid_request'}
        rows = [r for r in self.events.get(x['stream'], []) if x['start'] <= r['timestamp'] < x['end']]
        rows.sort(key=lambda r: (r['value'], r['timestamp'], r['event_id']))
        total = sum(r['weight'] for r in rows); value = None
        if rows:
            target = x['quantile'] * total
            acc = 0
            for r in rows:
                acc += r['weight']
                if acc >= target: value = r['value']; break
        return {'ok': True, 'stream': x['stream'], 'start': x['start'], 'end': x['end'], 'quantile': x['quantile'], 'value': value, 'weight': total, 'count': len(rows)}

    def request(self, x):
        if not isinstance(x, dict) or not isinstance(x.get('op'), str): return {'ok': False, 'error': 'invalid_request'}
        op = x['op']
        if op == 'reset':
            if 'lateness' in x and (not isinstance(x['lateness'], (int,float)) or x['lateness'] < 0): return {'ok': False, 'error': 'invalid_request'}
            self.clear(); self.lateness = x.get('lateness', 10); return {'ok': True}
        if op == 'ingest': return self.ingest(x)
        if op == 'query': return self.query(x)
        if op == 'checkpoint': return self.checkpoint()
        if op == 'recover': return self.recover()
        return {'ok': False, 'error': 'unknown_operation'}


def main():
    e = Engine()
    for line in sys.stdin:
        try: x = json.loads(line)
        except Exception: print(dump({'ok': False, 'error': 'invalid_request'}), flush=True); continue
        try: ans = e.request(x)
        except Exception: ans = {'ok': False, 'error': 'invalid_request'}
        print(dump(ans), flush=True)

if __name__ == '__main__': main()
