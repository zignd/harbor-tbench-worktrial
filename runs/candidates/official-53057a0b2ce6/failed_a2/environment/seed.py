import sqlite3, os
p='/opt/audit/state/audit.sqlite'
os.makedirs(os.path.dirname(p),exist_ok=True)
try: os.remove(p)
except FileNotFoundError: pass
c=sqlite3.connect(p)
c.executescript('''CREATE TABLE events(tenant TEXT NOT NULL, epoch INTEGER NOT NULL, seq INTEGER NOT NULL, payload BLOB NOT NULL, mac BLOB NOT NULL, PRIMARY KEY(tenant,epoch,seq)); CREATE TABLE epochs(tenant TEXT NOT NULL, epoch INTEGER NOT NULL, root BLOB NOT NULL, PRIMARY KEY(tenant,epoch));''')
# Seed records are intentionally simple and are repaired/replayed by the service.
for t in ('alpha','beta','gamma','delta'):
    for e in (0,1,2): c.execute('INSERT INTO epochs VALUES(?,?,?)',(t,e,b''))
    for i in (2,9,10,255,256): c.execute('INSERT INTO events VALUES(?,?,?,?,?)',(t,0,i,(f'{t}-{i}').encode(),b''))
c.commit(); c.close()
