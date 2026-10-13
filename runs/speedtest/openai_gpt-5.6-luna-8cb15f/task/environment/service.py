import glob,json,math,os,struct
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
F='/var/log/telemetry/frontend'; B='/var/log/telemetry/backend'

def load():
    fs=[]
    for fn in glob.glob(F+'/*.tsv'):
        with open(fn,errors='replace') as h:
            for line in h:
                p=line.rstrip('\n').split('\t')
                if len(p)>=6:
                    try: fs.append({'t':int(p[0]),'id':p[1],'endpoint':p[3],'status':int(p[4]),'lat':int(p[5])})
                    except ValueError: pass
    bs=[]
    for fn in glob.glob(B+'/*.bpack'):
        try:
            data=open(fn,'rb').read(); magic,ver,flags,n,base=struct.unpack_from('<4sBBHQ',data,0)
            if magic!=b'BPK1': continue
            pos=16; prev=base
            for _ in range(n):
                worker,ln,exitc,delta,dur=struct.unpack_from('<HBBiI',data,pos); pos+=12
                ep=data[pos:pos+ln].decode('utf-8'); pos+=ln; prev+=delta
                bs.append({'t':prev,'end':prev+dur,'worker':worker,'endpoint':ep,'exit':exitc,'lat':dur})
        except (OSError,struct.error,UnicodeDecodeError): pass
    fs.sort(key=lambda x:(x['t'],x['id'])); bs.sort(key=lambda x:(x['t'],x['worker']))
    return fs,bs

def attribute(fs,bs):
    edges=[]
    for i,f in enumerate(fs):
        for j,b in enumerate(bs):
            if b['endpoint']!=f['endpoint'] or not (f['t'] < b['t'] and b['end'] < f['t']+f['lat']): continue
            if b['exit'] and f['status'] not in (502,504): continue
            slack=(b['t']-f['t'])+(f['t']+f['lat']-b['end'])
            edges.append((slack,i,j))
    edges.sort(key=lambda x:(x[0],fs[x[1]]['t'],bs[x[2]]['t'],x[1],x[2]))
    chosen={}; usedb=set()
    def compatible(j, assignments, skip_i=None):
        b=bs[j]
        for oi,oj in assignments.items():
            if oi==skip_i: continue
            ob=bs[oj]
            if ob['worker']==b['worker'] and not (b['end']<=ob['t'] or b['t']>=ob['end']): return False
        return True
    def augment(i, seen, assignments):
        candidates=[e for e in edges if e[1]==i]
        for slack,fi,j in candidates:
            if j in seen: continue
            seen.add(j)
            owner=next((oi for oi,oj in assignments.items() if oj==j),None)
            if owner is None:
                if compatible(j,assignments): assignments[i]=j; return slack
            elif owner!=i:
                old=assignments.pop(owner)
                if compatible(j,assignments,skip_i=i):
                    assignments[i]=j
                    if augment(owner,seen,assignments) is not None: return slack
                    assignments.pop(i,None); assignments[owner]=old
                else: assignments[owner]=old
        return None
    for _,i,_ in edges:
        if i not in chosen: augment(i,set(),chosen)
    pairs=[]
    for i,j in chosen.items():
        f=fs[i]; b=bs[j]
        pairs.append((i,j,(b['t']-f['t'])+(f['t']+f['lat']-b['end'])))
    pairs.sort(); return pairs

def percentile(vals,p):
    if not vals:return None
    return sorted(vals)[max(0,math.ceil(p*len(vals))-1)]

def model():
    f,b=load(); pairs=attribute(f,b); return f,b,pairs

def result(q):
    f,b,pairs=model(); ep=q.get('endpoint'); lo,hi=q.get('time_range',[0,2**63-1])
    selected=[i for i,x in enumerate(f) if (ep is None or x['endpoint']==ep) and lo<=x['t']<hi]
    by={i:(j,s) for i,j,s in pairs}; mp=[by[i] for i in selected if i in by]
    vals=[b[j]['lat'] for j,s in mp]; bad=sum(1 for j,s in mp if b[j]['exit'])
    allv={'matched_count':len(mp),'unmatched_frontend_count':len(selected)-len(mp),'p50_backend_latency':percentile(vals,.50),'p90_backend_latency':percentile(vals,.90),'p99_backend_latency':percentile(vals,.99),'error_rate':(bad/len(mp) if mp else 0.0)}
    metrics=q.get('metrics') or list(allv); return {k:allv[k] for k in metrics if k in allv}

class H(BaseHTTPRequestHandler):
    def send(self,code,obj):
        raw=json.dumps(obj,separators=(',',':')).encode(); self.send_response(code); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        if self.path=='/healthz': self.send(200,{'status':'healthy'}); return
        if self.path=='/v1/attribution/stats':
            f,b,p=model(); self.send(200,{'total_frontend':len(f),'matched':len(p),'unmatched':len(f)-len(p),'matched_slacks':[x[2] for x in p],'backend_records':len(b)}); return
        self.send(404,{'error':'not found'})
    def do_POST(self):
        if self.path!='/v1/query': self.send(404,{'error':'not found'}); return
        try: q=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0')))); self.send(200,result(q))
        except Exception as e: self.send(400,{'error':str(e)})
    def log_message(self,*a): pass

if __name__=='__main__': ThreadingHTTPServer(('0.0.0.0',8085),H).serve_forever()
