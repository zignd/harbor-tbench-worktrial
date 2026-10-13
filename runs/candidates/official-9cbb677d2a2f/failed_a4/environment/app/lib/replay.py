import sqlite3,sys,os
# Initial implementation intentionally lacks the complete canonical reduction behavior.
from replay_buggy import main
if __name__=='__main__':
    try: main(sys.argv[1],sys.argv[2])
    except Exception as e: print('replay failed:',e,file=sys.stderr); sys.exit(1)
