import os,sqlite3,sys
from .pipeline import build
from .formatting import write_report
def main(argv=None):
 argv=sys.argv[1:] if argv is None else argv
 if len(argv)!=2:return 2
 db,out=argv
 c=sqlite3.connect('file:'+os.path.abspath(db)+'?mode=ro',uri=True)
 try:write_report(out,build(c))
 finally:c.close()
 return 0
