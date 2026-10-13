import sqlite3,json,binascii,os
os.makedirs('/workspace/data',exist_ok=True); p='/workspace/data/assay_catalog.sqlite'; c=sqlite3.connect(p)
c.executescript('create table runs(run_id text primary key,calibration_unit text,intercept real,slope real);create table unit_factors(unit text primary key,factor real);create table cohorts(cohort_id text primary key,treatment text,active integer);create table export_fragments(fragment_id integer primary key,run_id text,ordinal integer,payload blob);create table measurements(measurement_id integer primary key,cohort_id text,analyte text,well text,run_id text,sequence integer,observed_at integer,quality real,value real,unit text,role text,source_id text);create table controls(measurement_id integer primary key,kind text);')
c.execute("insert into runs values('run1','u',1,2)"); c.executemany('insert into unit_factors values(?,?)',[('u',1),('m',.001)]); c.execute("insert into cohorts values('C001','drug',1)")
def rec(i,role,v,w):
 d={'cohort_id':'C001','analyte':'A1','well':w,'run_id':'run1','sequence':1,'observed_at':i,'quality':1.0,'value':v,'unit':'u','role':role,'source_id':str(i)}; raw=json.dumps(d,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode(); d['crc32']=f'{binascii.crc32(raw)&0xffffffff:08x}'; return d
for i,(role,v,w) in enumerate([('positive_control',10,'P'),('negative_control',2,'N'),('pre',4,'A'),('post',8,'B')]):
 d=rec(i+1,role,v,w); s=(json.dumps(d,sort_keys=True,separators=(',',':'))+'\n').encode(); c.execute('insert into export_fragments(run_id,ordinal,payload) values(?,?,?)',('run1',i,s)); c.execute('insert into measurements values(?,?,?,?,?,?,?,?,?,?,?,?)',(i+1,'C001','A1',w,'run1',1,i+1,1,v,'u',role,str(i+1)))
c.commit();c.close()
