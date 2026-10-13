Repair the incident replay utility in /opt/replay. The public command is `node /opt/replay/bin/replay-incidents.js INPUT.sqlite OUTPUT.sqlite`.

Produce the documented canonical SQLite database from every valid input database. Preserve every source event and its exact original payload in archival_events, including the original actor value. Resolve actor aliases using their validity intervals at each event timestamp, and use the resolved identity for correlation while retaining the source actor for auditability. Correlate events by incident key and resolved actor, including documented merge links.

For each incident, produce a deterministic event order that satisfies source sequence and explicit dependency constraints. Missing optional dependencies do not create edges. If a valid dependency cycle exists, break it deterministically using the canonical event key specified by the repository documentation. Do not depend on insertion order, locale, or filesystem order.

Apply supersession, corrections, and tombstones before deriving transitions or SLA results. Superseded and tombstoned logical events must not affect canonical state, but all source rows remain archived. Evaluate the policy version effective at each transition timestamp, including incidents whose events cross policy boundaries.

Materialize deterministic incidents, incident_events, transitions, sla_windows, and replay_audit rows while preserving the documented SQLite schema. Replaying the same input into a fresh output, and replaying an already produced database where supported, must be idempotent. The output replacement must be atomic: an invalid or failed replay must not leave a partial destination.

Use the supplied README and docs/event-contract.md, inspect the implementation and exercise the CLI with multiple databases. The final command must continue to use the existing CLI and must work without network access.
