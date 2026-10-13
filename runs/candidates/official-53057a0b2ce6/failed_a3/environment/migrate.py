import sqlite3,sys
p=sys.argv[1] if len(sys.argv)>1 else '/opt/audit/state/audit.sqlite'
c=sqlite3.connect(p)
c.executescript('CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,tenant TEXT NOT NULL,epoch INTEGER NOT NULL,seq INTEGER NOT NULL,payload BLOB NOT NULL,mac TEXT NOT NULL,root TEXT NOT NULL); CREATE TABLE IF NOT EXISTS epochs(tenant TEXT NOT NULL,epoch INTEGER NOT NULL,root TEXT NOT NULL,signature TEXT,PRIMARY KEY(tenant,epoch));')
c.commit();c.close()
