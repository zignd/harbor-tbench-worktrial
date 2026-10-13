#!/usr/bin/env python3
"""Audit Log HMAC Chain Service - Protocol Handler"""

import sys
import os
import logging

sys.path.insert(0, "/app")

from audit_service import verifier
from audit_service import parser

LOG_DIR = "/app/logs"

logging.basicConfig(
    filename="/tmp/audit_service.log",
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("audit_service")


def resolve_logfile(name):
    if os.path.isabs(name):
        return name
    return os.path.join(LOG_DIR, name)


def handle_verify(parts, out):
    if len(parts) != 2:
        out.write("ERROR invalid VERIFY syntax\n")
        out.flush()
        return
    logfile = resolve_logfile(parts[1])
    log.debug("VERIFY %s", logfile)
    try:
        ok, value = verifier.verify_log(logfile)
        if ok:
            response = f"OK {value}\n"
        else:
            response = f"FAIL {value}\n"
    except FileNotFoundError:
        response = "FAIL 0\n"
    except parser.ParseError as exc:
        log.warning("ParseError for %s: %s", logfile, exc)
        response = "FAIL 0\n"
    except Exception as exc:
        log.error("Unexpected error for VERIFY %s: %s", logfile, exc)
        response = "FAIL 0\n"
    out.write(response)
    out.flush()


def handle_query(parts, out):
    if len(parts) != 3:
        out.write("NOTFOUND\n")
        out.flush()
        return
    logfile = resolve_logfile(parts[1])
    try:
        idx = int(parts[2])
    except ValueError:
        out.write("NOTFOUND\n")
        out.flush()
        return
    log.debug("QUERY %s %d", logfile, idx)
    try:
        payload = verifier.query_entry(logfile, idx)
    except Exception as exc:
        log.error("Unexpected error for QUERY %s %d: %s", logfile, idx, exc)
        payload = None
    if payload is None:
        out.write("NOTFOUND\n")
    else:
        out.write(payload + "\n")
    out.flush()


def main():
    log.info("Audit service starting")
    inp = sys.stdin
    out = sys.stdout
    try:
        for line in inp:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            parts = line.split()
            cmd = parts[0].upper() if parts else ""
            if cmd == "VERIFY":
                handle_verify(parts, out)
            elif cmd == "QUERY":
                handle_query(parts, out)
            else:
                log.warning("Unknown command: %r", line)
                out.write("ERROR unknown command\n")
                out.flush()
    except KeyboardInterrupt:
        pass
    log.info("Audit service exiting")


if __name__ == "__main__":
    main()
