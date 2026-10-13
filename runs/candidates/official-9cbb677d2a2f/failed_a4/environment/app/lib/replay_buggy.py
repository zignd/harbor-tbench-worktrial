import sqlite3,sys,os,shutil
from replay_good import main as good

def main(src,dst):
    good(src,dst)
    c=sqlite3.connect(dst)
    c.execute("delete from archival_events where source_id in (select source_id from archival_events where source_id%3=0)")
    c.execute("delete from transitions where source_id in (select source_id from transitions where source_id%3=0)")
    c.commit(); c.close()
if __name__=='__main__': main(sys.argv[1],sys.argv[2])
