import sqlite3,sys
d=sqlite3.connect(sys.argv[1]);o=open(sys.argv[2],'w')
for r in d.execute('select event_id,account,epoch,sequence from events order by epoch,sequence'):o.write('\t'.join(map(str,r))+'\n')
o.close()
