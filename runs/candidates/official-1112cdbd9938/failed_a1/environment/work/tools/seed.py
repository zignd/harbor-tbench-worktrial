import json, os, sqlite3
os.makedirs('/work/input', exist_ok=True); os.makedirs('/work/state', exist_ok=True)
with open('/work/input/archive.jsonl','w',encoding='utf-8') as f:
    for i in range(18000):
        d=1+i%28
        src=['192.0.2.%d'%(i%200+1),'2001:4860:4860::8888','::ffff:192.0.2.%d'%(i%200+1),'fe80::1%eth0'][i%4]
        r={'event_id':'evt-%05d'%(i%17000),'revision':2 if i==1 else 1,'timestamp':'2024-01-%02dT12:%02d:00Z'%(d,i%60),'actor':'用户' if i%997==0 else 'actor-%d'%(i%31),'source':src,'destination':'198.51.100.%d'%(i%200+1),'signature':'bad' if i%2333==0 else 'valid'}
        if i%1777==0: r['timestamp']='invalid'
        f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
with open('/work/input/archive.manifest','w') as f: f.write('archive.jsonl\n')
c=sqlite3.connect('/work/state/events.sqlite'); c.execute('create table stale(x)'); c.execute('insert into stale values(1)'); c.commit(); c.close()
