# Incident replay

Run `node /opt/incident-replay/bin/replay-incidents.js --input INPUT.sqlite --output OUTPUT.sqlite`.

Input tables are `raw_events(id,occurred_at,actor,kind,payload,source,seq,depends_on,correlation_key)`, `actor_aliases(alias,canonical,valid_from,valid_to)`, and `policy_versions(version,effective_from,effective_to,ack_minutes,resolve_minutes)`, plus optional `source_cursors` and `replay_metadata`. Dependencies are comma-separated ids. Alias intervals and policy intervals are half-open. Merge events use payload JSON `{"merge":"KEY"}`. Corrections use `corrects`, supersession uses `supersedes`, and tombstones use `tombstone` in payload.

Ordering, reduction, policy selection, atomicity, and the complete output schema are specified in `docs/event-contract.md`.
