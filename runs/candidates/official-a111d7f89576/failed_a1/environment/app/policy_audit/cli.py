import argparse, json, sqlite3
from .query import export_rows

def main(argv=None):
    p=argparse.ArgumentParser(prog='policy_audit')
    s=p.add_subparsers(dest='cmd',required=True)
    e=s.add_parser('export'); e.add_argument('--db',required=True); e.add_argument('--since',type=int,required=True); e.add_argument('--until',type=int,required=True)
    a=p.parse_args(argv)
    if a.cmd=='export':
        db=sqlite3.connect(a.db); db.row_factory=sqlite3.Row
        try:
            for r in export_rows(db,a.since,a.until): print(json.dumps(dict(r),separators=(',',':')))
        finally: db.close()
