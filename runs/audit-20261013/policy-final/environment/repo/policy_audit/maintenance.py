"""Operational helpers for inspecting an audit database."""
from .database import table_counts

def explain_export(con):
    statement = "SELECT request_sequence FROM access_requests WHERE event_ts >= ? AND event_ts < ?"
    return list(con.execute("EXPLAIN QUERY PLAN " + statement, (0, 1)))

def summary(con):
    counts = table_counts(con)
    counts["active_bindings"] = con.execute("SELECT count(*) FROM policy_bindings").fetchone()[0]
    counts["requests_with_ids"] = con.execute("SELECT count(DISTINCT request_id) FROM access_requests").fetchone()[0]
    return counts
