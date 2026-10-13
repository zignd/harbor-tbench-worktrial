import argparse, json, sqlite3
from .query import export_rows

def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m policy_audit")
    subs = parser.add_subparsers(dest="command", required=True)
    exp = subs.add_parser("export")
    exp.add_argument("--db", required=True)
    exp.add_argument("--since", required=True, type=int)
    exp.add_argument("--until", required=True, type=int)
    args = parser.parse_args(argv)
    if args.command == "export":
        con = sqlite3.connect(args.db)
        con.row_factory = sqlite3.Row
        try:
            for row in export_rows(con, args.since, args.until):
                print(json.dumps(dict(row), separators=(",", ":")))
        finally:
            con.close()

if __name__ == "__main__":
    main()
