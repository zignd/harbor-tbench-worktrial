#!/usr/bin/env python3
import argparse,json,os,glob,sys

def main():
 p=argparse.ArgumentParser();p.add_argument('--config',default='config.toml');p.add_argument('--input');p.add_argument('--output');a=p.parse_args()
 # Historical implementation: it parses documents independently and relies on traversal order.
 inp=a.input or 'contracts'; out=a.output or 'build'; entries=[]; errors=[]
 for fn in glob.glob(os.path.join(inp,'**','*.json'),recursive=True):
  try:
   x=json.load(open(fn)); name=x['name']; fields=x.get('fields',{}); policy=x.get('policy',{})
   if x.get('parent'): errors.append({'contract':name,'reason':'unresolved inheritance'}); continue
   if any(v.get('nullable') for v in fields.values() if isinstance(v,dict)) and not policy.get('allow_nullable',False): errors.append({'contract':name,'reason':'nullable fields are not allowed'});continue
   entries.append({'name':name,'fields':fields,'policy':policy})
  except Exception as e: errors.append({'contract':os.path.basename(fn),'reason':'malformed document'})
 os.makedirs(out,exist_ok=True)
 json.dump({'contracts':entries},open(os.path.join(out,'registry.json'),'w'),separators=(',',':'))
 with open(os.path.join(out,'diagnostics.ndjson'),'w') as f:
  for e in errors:f.write(json.dumps(e,separators=(',',':'))+'\n')
 json.dump({'accepted':len(entries),'rejected':len(errors)},open(os.path.join(out,'summary.json'),'w'),separators=(',',':'))
if __name__=='__main__':main()
