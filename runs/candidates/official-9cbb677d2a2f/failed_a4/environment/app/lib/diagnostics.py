import sqlite3,sys,json
if __name__=='__main__':
 c=sqlite3.connect(sys.argv[1]); c.row_factory=sqlite3.Row
 print(json.dumps({t:c.execute('select count(*) n from '+t).fetchone()['n'] for t in ('raw_events','actor_aliases','policy_versions')}))
