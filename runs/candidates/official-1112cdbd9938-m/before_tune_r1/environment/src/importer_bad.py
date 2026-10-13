#!/usr/bin/env python3
import json,sqlite3,os,sys,subprocess,datetime
DB='/work/state/events.sqlite'
def main():
 os.makedirs('/work/state',exist_ok=True)
 if os.path.exists(DB): os.unlink(DB)
 c=sqlite3.connect(DB); c.executescript('''create table events(event_id text,revision integer,timestamp text,actor text,source text,destination text,source_class text,destination_class text,signature text,risk integer,severity text,primary key(event_id)); create table rejections(source_file text,line_no integer,event_id text,revision integer,reason text); create table daily_summary(day text primary key,count integer,risk integer); create table actor_summary(actor text primary key,count integer,risk integer); create table indicator_summary(indicator text primary key,count integer); create table metadata(key text primary key,value text);''')
 for n,line in enumerate(open('/work/input/archive.jsonl',encoding='utf8'),1):
  try:
   x=json.loads(line); a=subprocess.check_output(['/opt/security/bin/addrclass'],input=(x['source']+'\n'+x['destination']).encode()).decode().split()
   if x.get('signature')!='valid': raise ValueError('signature')
   risk=len(a)+int(x['revision']); c.execute('insert or ignore into events values(?,?,?,?,?,?,?,?,?,?,?)',(x['event_id'],x['revision'],x['timestamp'],x['actor'],x['source'],x['destination'],a[0],a[2],x['signature'],risk,'low'))
  except Exception as e:c.execute('insert into rejections values(?,?,?,?,?)',('archive.jsonl',n,None,None,str(e)))
 c.commit(); c.close()
if __name__=='__main__':main()
