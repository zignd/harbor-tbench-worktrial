import argparse, json, sqlite3
from .query import export_rows

def main():
    parser = argparse.ArgumentParser(prog='policy_audit')
    sub = parser.add_subparsers(dest='command', required=True)
    exp = sub.add_parser('export')
    exp.add_argument('--db', required=True)
    exp.add_argument('--since', required=True, type=int)
    exp.add_argument('--until', required=True, type=int)
    args = parser.parse_args()
    if args.command == 'export':
        with sqlite3.connect(args.db) as db:
            db.row_factory = sqlite3.Row
            for row in export_rows(db, args.since, args.until):
                print(json.dumps(dict(row), separators=(',', ':'), sort_keys=True))
if __name__ == '__main__':
    main()
