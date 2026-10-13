import os,sqlite3
p='/opt/audit/state/audit.sqlite';os.makedirs(os.path.dirname(p),exist_ok=True)
try: os.unlink(p)
except FileNotFoundError: pass
c=sqlite3.connect(p)
c.executescript('CREATE TABLE events(id INTEGER PRIMARY KEY,tenant TEXT NOT NULL,epoch INTEGER NOT NULL,seq INTEGER NOT NULL,payload BLOB NOT NULL,mac TEXT NOT NULL,root TEXT NOT NULL); CREATE TABLE epochs(tenant TEXT NOT NULL,epoch INTEGER NOT NULL,root TEXT NOT NULL,signature TEXT,PRIMARY KEY(tenant,epoch)); CREATE UNIQUE INDEX event_key ON events(tenant,epoch,seq);')
c.commit();c.close()
