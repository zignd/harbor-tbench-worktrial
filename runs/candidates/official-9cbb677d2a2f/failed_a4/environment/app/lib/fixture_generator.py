import sqlite3,sys,random,json

def create(path,seed=1,count=20):
 r=random.Random(seed); c=sqlite3.connect(path)
 c.executescript('''create table raw_events(id integer primary key,source text,source_seq integer,occurred_at text,actor text,correlation text,event_type text,payload text,depends_on text,correction_of text,supersedes text); create table actor_aliases(alias text,canonical_actor text,valid_from text,valid_to text); create table policy_versions(version text primary key,effective_from text,effective_to text,ack_minutes integer,resolve_minutes integer); create table source_cursors(source text primary key,cursor integer); create table replay_metadata(key text primary key,value text);''')
 c.executemany('insert into actor_aliases values (?,?,?,?)',[('svc','alice','2024-01-01T00:00:00Z','2024-01-01T00:10:00Z'),('svc','bob','2024-01-01T00:10:00Z',None)])
 c.executemany('insert into policy_versions values (?,?,?,?,?)',[('early','2024-01-01T00:00:00Z','2024-01-01T00:10:00Z',5,20),('late','2024-01-01T00:10:00Z',None,3,10)])
 rows=[]
 for i in range(1,count+1):
  minute=i%18; typ='open' if i==1 else ('resolve' if i==count else ('ack' if i%4==0 else 'note'))
  dep=str(i-1) if i%5==0 else None
  rows.append((i,'generated',i,f'2024-01-01T00:{minute:02d}:00Z','svc','incident-'+str(i%3),typ,json.dumps({'n':i}),dep,None,None))
 r.shuffle(rows); c.executemany('insert into raw_events values (?,?,?,?,?,?,?,?,?,?,?)',rows); c.commit(); c.close()
if __name__=='__main__': create(sys.argv[1],int(sys.argv[2]) if len(sys.argv)>2 else 1,int(sys.argv[3]) if len(sys.argv)>3 else 20)
