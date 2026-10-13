import base64,json,math,struct,subprocess,socketserver

def crc16(b):
 c=65535
 for x in b:
  c^=x<<8
  for _ in range(8): c=((c<<1)^0x1021)&65535 if c&32768 else (c<<1)&65535
 return c

def eig(a):
 n=len(a);v=[[float(i==j) for j in range(n)] for i in range(n)]
 for z in range(max(1,80*n*n)):
  _,p,q=max((abs(a[i][j]),i,j) for i in range(n) for j in range(i+1,n)) if n>1 else (0,0,0)
  if _<1e-14: break
  t=.25*math.pi if abs(a[p][p]-a[q][q])<1e-30 else .5*math.atan2(2*a[p][q],a[p][p]-a[q][q]);c=math.cos(t);s=math.sin(t)
  for i in range(n):
   if i not in (p,q):
    x,y=a[i][p],a[i][q];a[i][p]=a[p][i]=c*x-s*y;a[i][q]=a[q][i]=s*x+c*y
  x,y,z=a[p][p],a[q][q],a[p][q];a[p][p]=c*c*x-2*s*c*z+s*s*y;a[q][q]=s*s*x+2*s*c*z+c*c*y;a[p][q]=a[q][p]=0
  for i in range(n): x,y=v[i][p],v[i][q];v[i][p]=c*x-s*y;v[i][q]=s*x+c*y
 ix=sorted(range(n),key=lambda i:a[i][i],reverse=True);vals=[a[i][i] for i in ix];cols=[]
 for k in ix:
  x=[v[i][k] for i in range(n)];q=math.sqrt(sum(y*y for y in x));x=[y/q for y in x];j=max(range(n),key=lambda i:abs(x[i]));cols.append([-y for y in x] if x[j]<0 else x)
 return vals,cols
class R:
 def __init__(self,x):self.id=x['run_id'];self.n=x['channels'];self.rev=x['calibration'];self.m=x['modes'];self.f={};self.c={};self.bad=0;self.dup=0;self.done=None
 def frame(self,x):
  try:b=base64.b64decode(x['data'],validate=True);ok=len(b)==2*self.n+2 and crc16(b[:-2])==struct.unpack('<H',b[-2:])[0]
  except Exception:ok=False
  if not ok:self.bad+=1;return {'ok':False,'error':'BAD_FRAME'}
  if x['seq'] in self.f:self.dup+=1
  self.f[x['seq']]=list(struct.unpack('<%dh'%self.n,b[:-2]));return {'ok':True,'accepted':True,'seq':x['seq']}
 def report(self):
  o=[]
  for k in sorted(self.f):
   x=[self.f[k][i]+self.c.get(k,[0]*self.n)[i] for i in range(self.n)];x=[int(math.floor(y+.5) if y>=0 else math.ceil(y-.5)) for y in x];q=struct.pack('<IHH',self.rev,self.n,self.m)+struct.pack('<%dh'%self.n,*x);o.append(list(struct.unpack('<%dd'%self.m,subprocess.check_output(['/usr/local/libexec/modalcodec'],input=q))))
  d=self.m;n=len(o);mean=[sum(x[j] for x in o)/n if n else 0 for j in range(d)];cov=[[sum((x[i]-mean[i])*(x[j]-mean[j]) for x in o)/(n-1) if n>1 else 0 for j in range(d)] for i in range(d)];ev,vec=eig([x[:] for x in cov]);ev=[0 if -1e-10<x<0 else x for x in ev];ks=sorted(self.f);miss=ks[-1]-ks[0]+1-len(ks) if ks else 0
  return {'run_id':self.id,'calibration':self.rev,'counts':{'accepted':len(ks),'rejected':self.bad,'duplicate':self.dup,'missing':miss},'mean':mean,'covariance':cov,'eigenvalues':ev,'eigenvectors':vec}
class H(socketserver.StreamRequestHandler):
 def handle(self):
  rs={}
  for line in self.rfile:
   try:x=json.loads(line);op=x.get('op');rid=x.get('run_id');r=rs.get(rid)
   except: self.wfile.write(b'{"ok":false,"error":"JSON"}\n');continue
   try:
    if op=='begin':
     if r:raise ValueError('ORDER')
     rs[rid]=R(x);a={'ok':True,'op':'begin'}
    elif not r:raise ValueError('UNKNOWN_RUN')
    elif op=='frame' and r.done is None:a=r.frame(x)
    elif op=='correction' and r.done is None and len(x.get('corrections',[]))==r.n:r.c[x['seq']]=list(map(float,x['corrections']));a={'ok':True,'op':'correction'}
    elif op=='finalize' and r.done is None:r.done=r.report();a={'ok':True,'report':r.done}
    elif op=='query' and r.done is not None:a={'ok':True,'report':r.done}
    else:raise ValueError('ORDER')
   except ValueError as e:a={'ok':False,'error':str(e)}
   except Exception:a={'ok':False,'error':'INVALID'}
   self.wfile.write((json.dumps(a,separators=(',',':'))+'\n').encode());self.wfile.flush()
class S(socketserver.ThreadingTCPServer):allow_reuse_address=True
if __name__=='__main__':
 with S(('0.0.0.0',7077),H) as s:s.serve_forever()
