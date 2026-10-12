"""Command-line interface for the ledger tool."""
import sys


def usage():
    print("Usage: python -m ledger <command> [args]")
    print("")
    print("Commands:")
    print("  import <exports_dir>   Import CSV exports into the ledger")
    print("  report <exports_dir>   Import and print per-merchant balance report")
    sys.exit(1)


def main():
    if len(sys.argv) < 2:
        usage()

    command = sys.argv[1]

    if command == "import":
        if len(sys.argv) < 3:
            print("Error: import requires <exports_dir>", file=sys.stderr)
            sys.exit(1)
        exports_dir = sys.argv[2]
        from .importer import import_exports
        n = import_exports(exports_dir)
        print(f"Imported {n} transactions.")

    elif command == "report":
        if len(sys.argv) < 3:
            print("Error: report requires <exports_dir>", file=sys.stderr)
            sys.exit(1)
        exports_dir = sys.argv[2]
        from .report import run_report
        run_report(exports_dir)

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        usage()
