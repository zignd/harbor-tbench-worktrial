import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
MODE = 'buggy'
EVENTS = {}

def ts(value):
    if not isinstance(value, str): raise ValueError('timestamp')
    d = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if d.tzinfo is None: raise ValueError('timezone')
    return d.astimezone(timezone.utc).timestamp()

def key(e):
    return (ts(e['occurred_at']), int(e['ingest_seq']), str(e['event_id']))

def build():
    users = {}
    for e in EVENTS.values(): users.setdefault(e['user_id'], []).append(e)
    membership, session_events, touches = {}, {}, {}
    for user, es in users.items():
        es.sort(key=key)
        previous = None
        number = -1
        for e in es:
            current = ts(e['occurred_at'])
            if previous is None or current - previous > 1800:
                number += 1
            sid = (user, number)
            membership[e['event_id']] = sid
            session_events.setdefault(sid, []).append(e)
            if e.get('kind') == 'touch':
                touches.setdefault(sid, []).append(e)
            previous = current
    session_campaign = {}
    for sid, es in session_events.items():
        touch = [e for e in touches.get(sid, []) if e.get('campaign') is not None]
        session_campaign[sid] = touch[-1]['campaign'] if touch else '(direct)'
    orders = {}
    for e in EVENTS.values():
        if e.get('kind') != 'purchase' or e.get('order_id') is None: continue
        oid = str(e['order_id'])
        old = orders.get(oid)
        if old is not None and (int(old['ingest_seq']), str(old['event_id'])) >= (int(e['ingest_seq']), str(e['event_id'])): continue
        sid = membership[e['event_id']]
        prior = [x for x in touches.get(sid, []) if ts(x['occurred_at']) <= ts(e['occurred_at'])]
        campaign = prior[-1].get('campaign') if prior else '(direct)'
        orders[oid] = {'event': e, 'campaign': campaign, 'session': sid, 'refund': None}
    for e in EVENTS.values():
        if e.get('kind') == 'refund' and e.get('order_id') is not None:
            order = orders.get(str(e['order_id']))
            if order is not None and (order.get('refund') is None or key(e) < key(order['refund'])): order['refund'] = e
    return membership, session_events, session_campaign, orders

def make_report(q):
    membership, sessions, campaigns, orders = build()
    since = ts(q['since']) if q.get('since') is not None else float('-inf')
    until = ts(q['until']) if q.get('until') is not None else float('inf')
    requested = q.get('campaigns')
    if requested is None and isinstance(q.get('campaign'), str): requested = [q['campaign']]
    if requested is not None and not isinstance(requested, list): raise ValueError('campaigns')
    values = {}
    def get(c):
        return values.setdefault(c, {'sessions': set(), 'purchases': 0, 'revenue': 0})
    def in_range(e):
        return since <= ts(e['occurred_at']) < until
    # Refunds reverse orders but do not create standalone funnel sessions.
    for sid, es in sessions.items():
        if any(in_range(e) and e.get('kind') in ('touch', 'purchase') for e in es):
            get(campaigns[sid])['sessions'].add(sid)
    for order in orders.values():
        purchase = order['event']; campaign = order['campaign']; sid = order['session']
        if in_range(purchase):
            row = get(campaign); row['sessions'].add(sid)
            row['purchases'] += 1
            row['revenue'] += int(purchase.get('amount_cents', 0))
        refund = order['refund']
        if refund is not None and in_range(refund):
            get(campaign)['revenue'] -= int(purchase.get('amount_cents', 0))
    names = set(values) if requested is None else set(requested)
    result = []
    for name in names:
        row = values.get(name, {'sessions': set(), 'purchases': 0, 'revenue': 0})
        result.append({'campaign_name': name, 'session_count': len(row['sessions']), 'purchase_count': row['purchases'], 'net_revenue_cents': row['revenue']})
    result.sort(key=lambda r: (-r['net_revenue_cents'], r['campaign_name']))
    if MODE == 'buggy' and result:
        result[0]['net_revenue_cents'] += 1
    return result

class Handler(BaseHTTPRequestHandler):
    def answer(self, status, obj):
        body = json.dumps(obj, separators=(',', ':')).encode()
        self.send_response(status); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if self.path == '/health': self.answer(200, {'status': 'ok'})
        else: self.answer(404, {'error': 'not found'})
    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            data = json.loads(self.rfile.read(length) or b'{}')
            if self.path == '/v1/reset':
                if not isinstance(data, dict): raise ValueError()
                EVENTS.clear(); self.answer(200, {'ok': True}); return
            if self.path == '/v1/append':
                batch = data['events']
                if not isinstance(batch, list): raise ValueError()
                for e in batch:
                    if not isinstance(e, dict): raise ValueError()
                    for field in ('event_id','user_id','occurred_at','ingest_seq','kind'):
                        if field not in e: raise ValueError()
                    ts(e['occurred_at']); int(e['ingest_seq'])
                for e in batch:
                    old = EVENTS.get(str(e['event_id']))
                    if old is None or int(e['ingest_seq']) > int(old['ingest_seq']): EVENTS[str(e['event_id'])] = e
                self.answer(200, {'accepted': len(batch)}); return
            if self.path == '/v1/report':
                self.answer(200, {'rows': make_report(data)}); return
            self.answer(404, {'error': 'not found'})
        except Exception:
            self.answer(400, {'error': 'invalid request'})
    def log_message(self, *args): pass

if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
