#!/usr/bin/env python3
import json, os, re, sqlite3, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def merge(a,b):
    out=dict(a)
    for k,v in b.items():
        out[k]=merge(out[k],v) if isinstance(v,dict) and isinstance(out.get(k),dict) else v
    return out

def config():
    result={}
    channel=os.environ.get('RELEASE_CHANNEL','stable')
    for p in [ROOT/'config/base.json',ROOT/f'config/channels/{channel}.json',ROOT/'config/local.json']:
        if p.exists(): result=merge(result,json.loads(p.read_text(encoding='utf8')))
    return result

def manifest(path):
    sections=[]; current=None; lines=path.read_text(encoding='utf8').splitlines(); i=0
    while i<len(lines):
        raw=lines[i]; i+=1; s=raw.strip()
        if not s or s.startswith('#'): continue
        m=re.fullmatch(r'\[([^\]]+)\]',s)
        if m: current={'name':m.group(1)}; sections.append(current); continue
        if current is None or '=' not in raw: continue
        key,val=raw.split('=',1); key=key.strip(); val=val.strip()
        if val.startswith('"""'):
            val=val[3:]; parts=[]
            if val.endswith('"""'): val=val[:-3]
            else:
                if val: parts.append(val)
                while i<len(lines):
                    q=lines[i]; i+=1
                    if q.strip().endswith('"""'):
                        parts.append(q[:q.rfind('"""')]); break
                    parts.append(q)
                val='\n'.join(parts)
        elif val.startswith('{'):
            val=json.loads(val)
        elif len(val)>=2 and val[0]==val[-1]=='"':
            val=json.loads(val)
        current[key]=val
    return sections

def query_for(rel):
    p=ROOT/rel
    if p.is_file(): return p.read_text(encoding='utf8')
    hashes=subprocess.run(['git','log','--all','--format=%H','--',rel],cwd=ROOT,text=True,capture_output=True,check=False).stdout.splitlines()
    for h in hashes:
        x=subprocess.run(['git','show',f'{h}:{rel}'],cwd=ROOT,text=True,capture_output=True,check=False)
        if x.returncode==0: return x.stdout
    raise FileNotFoundError(rel)

def translate(sql, params):
    out=[]; binds=[]; i=0; mode='code'; dollar=None
    while i<len(sql):
        c=sql[i]
        if mode=='sq':
            out.append(c); i+=1
            if c=="'":
                if i<len(sql) and sql[i]=="'": out.append("'"); i+=1
                else: mode='code'
            continue
        if mode=='dq':
            out.append(c); i+=1
            if c=='"': mode='code'
            continue
        if mode=='line':
            out.append(c); i+=1
            if c=='\n': mode='code'
            continue
        if mode=='block':
            if sql.startswith('*/',i): out.append('*/'); i+=2; mode='code'
            else: out.append(c); i+=1
            continue
        if dollar:
            if sql.startswith(dollar,i): out.append(dollar); i+=len(dollar); dollar=None; mode='code'
            else: out.append(c); i+=1
            continue
        if c=="'": mode='sq'; out.append(c); i+=1; continue
        if c=='"': mode='dq'; out.append(c); i+=1; continue
        if sql.startswith('--',i): mode='line'; out.append('--'); i+=2; continue
        if sql.startswith('/*',i): mode='block'; out.append('/*'); i+=2; continue
        if sql.startswith('::',i):
            m=re.match(r'::\s*[A-Za-z_][A-Za-z_0-9]*(?:\[\])?',sql[i:])
            if m: i+=len(m.group(0)); continue
        if c=='$':
            m=re.match(r'\$[A-Za-z_][A-Za-z_0-9]*\$|\$\$',sql[i:])
            if m: dollar=m.group(0); out.append(dollar); i+=len(dollar); continue
            m=re.match(r'\$(\d+|[A-Za-z_][A-Za-z_0-9]*)',sql[i:])
            if m:
                key=m.group(1); key=int(key) if key.isdigit() else key
                if key not in params: raise KeyError(str(key))
                binds.append(params[key]); out.append('?'); i+=len(m.group(0)); continue
        m=re.match(r'[A-Za-z_][A-Za-z_0-9]*',sql[i:])
        if m:
            word=m.group(0); upper=word.upper()
            if upper=='TRUE': out.append('1')
            elif upper=='FALSE': out.append('0')
            else: out.append(word)
            i+=len(word); continue
        out.append(c); i+=1
    text=''.join(out)
    text=re.sub(r'(?i)(\S+)\s+ILIKE\s+(\S+)',r'lower(\1) LIKE lower(\2)',text)
    return text,binds

def main():
    os.chdir(ROOT); art=ROOT/'artifacts'; art.mkdir(exist_ok=True)
    for p in [art/'report-results.sqlite',art/'report-errors.json']:
        if p.exists(): p.unlink()
    db=sqlite3.connect(art/'report-results.sqlite')
    db.execute('create table events(id integer,status text,amount)')
    for line in (ROOT/'data/events.ndjson').read_text(encoding='utf8').splitlines():
        if line.strip():
            v=json.loads(line); db.execute('insert into events values (?,?,?)',(v.get('id'),v.get('status'),v.get('amount')))
    db.execute('create table report_results(report_name text,row_index integer,data text,primary key(report_name,row_index))')
    sections={x['name']:x for x in manifest(ROOT/'reports/release.manifest')}; errors=[]
    for name,setting in config().get('reports',{}).items():
        if not setting.get('enabled',True): continue
        active=False
        try:
            db.execute('savepoint report'); active=True
            if name not in sections: raise ValueError('manifest section missing')
            sec=sections[name]; params=dict(sec.get('params',{})); params.update(setting.get('params',{})); params.update({int(k):v for k,v in params.items() if str(k).isdigit()})
            rel=setting.get('query',sec.get('query'))
            sql=query_for(rel) if rel else sec.get('sql','')
            q,b=translate(sql,params); cur=db.execute(q,b); rows=cur.fetchall(); cols=[d[0] for d in cur.description] if cur.description else []
            for n,row in enumerate(rows): db.execute('insert into report_results values (?,?,?)',(name,n,json.dumps(dict(zip(cols,row)),ensure_ascii=False,separators=(',',':'))))
            db.execute('release report'); active=False
        except Exception as e:
            if active:
                try: db.execute('rollback to report')
                except sqlite3.Error: pass
                try: db.execute('release report')
                except sqlite3.Error: pass
            errors.append({'report':name,'category':'execution','message':str(e)})
    db.commit(); db.close(); (art/'report-errors.json').write_text(json.dumps(errors,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf8')
if __name__=='__main__': main()
