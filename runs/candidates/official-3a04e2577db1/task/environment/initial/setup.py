import sqlite3, os, json
os.makedirs('/work/sqlgate/samples', exist_ok=True)
p='/work/sqlgate/samples/device.db'
try: os.unlink(p)
except FileNotFoundError: pass
c=sqlite3.connect(p)
c.executescript('create table telemetry(id integer, value text); create table secret(x text); create table policy(table_name text,column_name text,allowed integer); insert into telemetry values(1,"ok"); insert into secret values("hidden"); insert into policy values("telemetry",null,1);')
c.commit(); c.close()
with open('/work/sqlgate/samples/requests.ndjson','w') as f:
 for i,s in enumerate(['select id from telemetry','select x from secret','insert into telemetry values(2,\'x\')','bad sql','select * from telemetry where id=?']):
  f.write(json.dumps({'id':i,'sql':s,'params':[1]},separators=(',',':'))+'\n')
