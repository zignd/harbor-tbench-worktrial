#!/usr/bin/env python3
import json, os, sqlite3
DB='/work/state/events.sqlite'
def main():
    os.makedirs('/work/state',exist_ok=True)
    if os.path.exists(DB): os.unlink(DB)
    c=sqlite3.connect(DB)
    c.executescript('create table events(event_id text primary key, revision integer, timestamp text, actor text, source text, destination text, source_class text, destination_class text, signature text, risk integer, severity text); create table rejections(source_file text,line_no integer,event_id text,revision integer,reason text,raw text); create table daily_summary(day text primary key,event_count integer,total_risk integer,low_count integer,medium_count integer,high_count integer); create table actor_summary(actor text primary key,event_count integer,total_risk integer); create table indicator_summary(indicator text primary key,event_count integer,total_risk integer); create table metadata(key text primary key,value text)')
    try:
        f=open('/work/input/archive.jsonl',encoding='utf8')
        for n,line in enumerate(f,1):
            try:
                x=json.loads(line)
                c.execute('insert or ignore into events values(?,?,?,?,?,?,?,?,?,?,?)',(x['event_id'],x.get('revision',1),x['timestamp'],x['actor'],x['source'],x['destination'],'unknown','unknown','valid',0,'low'))
            except Exception as e:
                c.execute('insert into rejections values(?,?,?,?,?,?)',('archive.jsonl',n,None,None,'invalid',line.rstrip()))
    except Exception: pass
    c.commit(); c.close()
if __name__=='__main__': main()
