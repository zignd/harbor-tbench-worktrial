import os, shutil, sqlite3
r='/opt/ledgerdash'
for p in (r, r+'/bin', r+'/config', r+'/fixtures', r+'/vendor', r+'/dist', '/var/lib/ledgerdash', '/srv/ledgerdash/releases'):
    os.makedirs(p, exist_ok=True)
open(r+'/config/default.json','w').write('{"release":"1.0.0","minor_scale":2}\n')
open(r+'/vendor/amount-normalizer','w').write('amount-normalizer-opaque-1\n')
os.chmod(r+'/vendor/amount-normalizer',0o755)
open(r+'/fixtures/visible-events.ndjson','w').write('\n'.join([
    '{"id":"c1","account":"research","currency":"USD","kind":"charge","amount":"101.00"}',
    '{"id":"r1","account":"research","currency":"USD","kind":"refund","amount":"0","ref":"c1"}',
    '{"id":"a1","account":"research","currency":"USD","kind":"adjustment","amount":"0.99"}'
])+'\n')
open(r+'/bin/ledgerdash','w').write('#!/bin/sh\n[ "${1:-}" = report ] && echo ledgerdash report\n')
os.chmod(r+'/bin/ledgerdash',0o755)
try: os.remove('/var/lib/ledgerdash/report.db')
except FileNotFoundError: pass
c=sqlite3.connect('/var/lib/ledgerdash/report.db')
c.execute('create table events(id text)')
c.execute('insert into events values("stale")')
c.commit(); c.close()
open('/var/lib/ledgerdash/events.ndjson','w').write('')
