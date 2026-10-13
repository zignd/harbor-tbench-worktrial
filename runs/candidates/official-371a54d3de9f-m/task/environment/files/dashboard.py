#!/usr/bin/env python3
import sqlite3,sys
p=sys.argv[1] if len(sys.argv)>1 else '/opt/incident/data/sample.db'
c=sqlite3.connect(p)
for t in ('epochs','key_shares','audit_events','chain_anchors','terminal_checkpoints'):
 print('%s %d'%(t,c.execute('select count(*) from '+t).fetchone()[0]))
