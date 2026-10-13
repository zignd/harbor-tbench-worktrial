import os,sqlite3,json,zlib
from assay_report.recover import body_crc
os.makedirs('/workspace/data',exist_ok=True); p='/workspace/data/assay_catalog.sqlite'
try: os.unlink(p)
except FileNotFoundError: pass
c=sqlite3.connect(p);c.executescript('''create table runs(run_id text,priority integer,calibration_unit text,slope real,intercept real);create table unit_factors(unit text,factor real);create table measurements(measurement_id text,run_id text,cohort_id text,analyte text,well text,sequence integer,timestamp text,quality real,phase text,value real,unit text,crc32 text);create table export_fragments(fragment_id integer primary key,run_id text,fragment_no integer,payload blob);create table controls(control_id text,cohort_id text,analyte text,kind text,run_id text,well text,sequence integer,timestamp text,quality real,value real,unit text,crc32 text);create table cohorts(cohort_id text primary key)''')
c.executemany('insert into unit_factors values (?,?)',[('u',1),('m',1000)]);c.execute('insert into runs values (?,?,?,?,?)',('r',1,'u',1,0));c.executemany('insert into cohorts values (?)',[('c1',),('empty',)])
def rec(i,z,phase,v):
 o={'measurement_id':i,'run_id':'r','cohort_id':z,'analyte':'A','well':i,'sequence':1,'timestamp':'1','quality':1.0,'phase':phase,'value':float(v),'unit':'u'};o['crc32']=str(body_crc(o));return o
for i,(ph,v) in enumerate([('pre',1),('post',2)],1):
 o=rec(str(i),'c1',ph,v);c.execute('insert into measurements values (?,?,?,?,?,?,?,?,?,?,?,?)',tuple(o.values()))
for j,(kind,v) in enumerate([('positive',2),('negative',0)]):
 o={'control_id':'k'+str(j),'cohort_id':'c1','analyte':'A','kind':kind,'run_id':'r','well':'k'+str(j),'sequence':1,'timestamp':'1','quality':1.0,'value':float(v),'unit':'u'};o['crc32']=str(body_crc(o));c.execute('insert into controls values (?,?,?,?,?,?,?,?,?,?,?,?)',tuple(o.values()))
c.commit();c.close()
