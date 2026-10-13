import sqlite3, json, zlib, os
base=os.path.dirname(os.path.abspath(__file__))
p=os.path.join(base,'data'); os.makedirs(p,exist_ok=True)
db=os.path.join(p,'assay_catalog.sqlite')
if os.path.exists(db): os.remove(db)
c=sqlite3.connect(db); c.executescript('''CREATE TABLE runs(run_id TEXT PRIMARY KEY,slope REAL,intercept REAL,calibration_unit TEXT); CREATE TABLE export_fragments(fragment_id INTEGER PRIMARY KEY,payload BLOB); CREATE TABLE measurements(measurement_id TEXT PRIMARY KEY,cohort TEXT,analyte TEXT,run_id TEXT,well TEXT,sequence INTEGER,quality REAL,timestamp INTEGER,value REAL,unit TEXT,crc32 TEXT,fragment_id INTEGER); CREATE TABLE controls(measurement_id TEXT,cohort TEXT,analyte TEXT,role TEXT); CREATE TABLE cohorts(cohort TEXT PRIMARY KEY,analyte TEXT,include INTEGER); CREATE TABLE unit_factors(unit TEXT PRIMARY KEY,factor REAL);''')
c.executemany('INSERT INTO runs VALUES(?,?,?,?)',[('r1',2,1,'u'),('r2',1.5,-2,'u')]); c.executemany('INSERT INTO unit_factors VALUES(?,?)',[('u',1),('m',1000)]); c.executemany('INSERT INTO cohorts VALUES(?,?,?)',[('c1','a',1),('c2','a',1),('empty','a',1)])
def rec(i,co='c1',role='sample',v=3,unit='u',run='r1',seq=1,q=1):
 d={'id':i,'cohort':co,'analyte':'a','run':run,'well':'w'+i,'seq':seq,'quality':q,'timestamp':1,'value':v,'unit':unit,'role':role}; raw=json.dumps(d,sort_keys=True,separators=(',',':')).encode(); d['crc32']=f'{zlib.crc32(raw)&0xffffffff:08x}'; return json.dumps(d,separators=(',',':'))
lines=[rec('s1'),rec('p1',role='positive',v=1),rec('s2',v=5),rec('n1',role='negative',v=0)]
c.execute('INSERT INTO export_fragments VALUES(?,?)',(1,('\n'.join(lines)+'\n').encode())); c.commit(); c.close()
