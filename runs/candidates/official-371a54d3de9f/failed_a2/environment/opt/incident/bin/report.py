#!/usr/bin/env python3
import sqlite3,sys
if __name__=='__main__':
    d=sqlite3.connect(sys.argv[1]);o=open(sys.argv[2],'w',encoding='utf8')
    for r in d.execute('select event_id,account,epoch,sequence from events order by epoch,sequence'):
        o.write('\t'.join(map(str,r))+'\n')
    o.close()
