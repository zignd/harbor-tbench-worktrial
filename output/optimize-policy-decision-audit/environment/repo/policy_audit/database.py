"""Database setup and read-only connection helpers."""
import sqlite3
from pathlib import Path

SCHEMA = Path(__file__).resolve().parent.parent / "schema.sql"

def connect(path):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con

def initialize(path):
    con = connect(path)
    try:
        con.executescript(SCHEMA.read_text())
        con.commit()
    finally:
        con.close()

def table_counts(con):
    names = ("tenants", "policy_definitions", "policy_revisions", "policy_bindings", "access_requests")
    return {name: con.execute(f"SELECT count(*) FROM {name}").fetchone()[0] for name in names}

def integrity_check(con):
    return con.execute("PRAGMA integrity_check").fetchone()[0]
