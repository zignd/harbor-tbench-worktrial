import hashlib,json,os,sys
from pathlib import Path
root=Path(sys.argv[1]); (root/'ci').mkdir(parents=True,exist_ok=True); (root/'catalog').mkdir(exist_ok=True); (root/'payload').mkdir(exist_ok=True)
cats=[]; events=[]
N=6000
for i in range(N):
    ident=f'node/{i}'; data=f'fixture-payload-{i}'.encode(); digest=hashlib.sha256(data).hexdigest()
    (root/'payload'/digest).write_bytes(data)
    cats.append({'identity':ident,'path':f'payload/{digest}','digest':digest,'size':len(data),'platform':'linux','variant':'release','dependencies':[f'node/{i+1}'] if i+1<N else []})
    events.append({'job':f'job-{i}','attempt':1,'status':'success','artifact':ident,'platform':'linux','variant':'release'})
(root/'release.yaml').write_text(json.dumps({'name':'large-fixture','platform':'linux','variant':'release','roots':['node/0']}))
(root/'catalog/artifacts.jsonl').write_text(''.join(json.dumps(x,separators=(',',':'))+'\n' for x in cats))
(root/'ci/build-events.jsonl').write_text(''.join(json.dumps(x,separators=(',',':'))+'\n' for x in events))
