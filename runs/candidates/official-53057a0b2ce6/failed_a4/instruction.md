Restore the audit service in /opt/audit so /opt/audit/bin/start.sh runs a JSON-lines TCP service on 127.0.0.1:7070. Preserve the health, append, query, rotate, verify, and reset request types and JSON response framing.

Append requests contain tenant, epoch, seq, and a base64 payload. Return ok, tenant, epoch, seq, payload, mac, and root. Payloads may contain NUL and non-UTF-8 bytes. MACs and roots must follow /opt/audit/PROTOCOL.md and remain valid after restart.

Query requests contain tenant and optional epoch, seq_min, seq_max, prefix, offset, and limit. Return ok, events, total, offset, and limit. Match all filters, order numerically by seq, and paginate after filtering. Event objects contain tenant, epoch, numeric seq, payload, and mac. Tenant and epoch identities are composite.

Rotate requests contain tenant, epoch, and new_epoch and return ok, tenant, old_epoch, new_epoch, transition, and root with valid transition metadata. Verify must remain valid after arbitrary operations and restarts. Reset with scope tenant clears only that tenant; reset without that scope clears all tenants. Preserve SQLite state and records outside the requested reset scope. Support sequence values 0, 1, 2, 9, 10, 255, 256, and larger values.
