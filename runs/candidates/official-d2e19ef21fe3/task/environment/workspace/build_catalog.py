import sqlite3,json,zlib,os
p='/workspace/data/assay_catalog.sqlite';os.makedirs('/workspace/data',exist_ok=True)
try:os.remove(p)
except FileNotFoundError:pass
c=sqlite3.connect(p);c.executescript('create table runs(run_id text primary key,slope real,intercept real,calibration_unit text);create table export_fragments(fragment_id integer primary key,payload blob);create table measurements(measurement_id text primary key,cohort text,analyte text,run_id text,well text,sequence integer,quality real,timestamp integer,value real,unit text,crc32 text,fragment_id integer);create table controls(measurement_id text,cohort text,analyte text,role text);create table cohorts(cohort text,analyte text,include integer default 1,primary key(cohort,analyte));create table unit_factors(unit text primary key,factor real)')
c.execute("insert into runs values('r1',2,1,'u')");c.executemany('insert into unit_factors values(?,?)',[('u',1),('m',1000)])
for co,a,inc in [('alpha','x',1),('alpha','y',1),('empty','x',1),('excluded','x',0)]:c.execute('insert into cohorts values(?,?,?)',(co,a,inc))
def add(i,co,a,role,v,well,seq=1,q=1,unit='u'):
 d={'id':i,'cohort':co,'analyte':a,'run':'r1','well':well,'seq':seq,'quality':q,'timestamp':1,'value':v,'unit':unit,'role':role};x=json.dumps(d,sort_keys=True,separators=(',',':')).encode();d['crc32']=f'{zlib.crc32(x)&0xffffffff:08x}';return json.dumps(d,separators=(',',':'))
lines=[add('s1','alpha','x','sample',2,'w1'),add('p1','alpha','x','positive',1,'p1'),add('y1','alpha','y','sample',3,'y1'),'{malformed',add('s2','alpha','x','sample',4,'w2'),add('bad','alpha','x','sample',99,'bad')[:-5]]
raw=('\n'.join(lines)+'\n').encode();c.executemany('insert into export_fragments values(?,?)',[(1,raw[:73]),(2,raw[73:])]);c.commit();c.close()
