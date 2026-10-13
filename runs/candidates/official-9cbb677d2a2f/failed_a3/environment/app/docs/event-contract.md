# Event contract

`raw_events` has `(id, occurred_at, actor, kind, payload, source, seq, depends_on, correlation_key)`. Timestamps are normalized UTC text. Alias intervals are half-open `[valid_from, valid_to)`, with a null upper bound meaning unbounded. The alias valid at the event timestamp is selected before correlation.

Correlation starts with `correlation_key`, otherwise the resolved actor. A payload `{"merge":"KEY"}` joins the event's component to KEY. Dependencies are comma-separated event ids; a missing optional dependency is ignored. A stable topological order uses `(source sequence, timestamp, event id)` and, when no node is available, removes the smallest event id as the cycle break.

Payload keys `corrects`, `supersedes`, and `tombstone` identify logical events. Reduction occurs after ordering; replaced or tombstoned events remain archived and in membership rows but do not produce transitions or SLA effects. Policy intervals are half-open and selected independently at every event timestamp.

Output schemas are:

* `archival_events(event_id, occurred_at, original_actor, resolved_actor, payload, source_id, source_sequence, kind, archived_at)`; payload and original actor are immutable, while normalized time and resolved actor are derived.
* `incidents(incident_id, correlation_key, opened_at, resolved_at, status, owner, event_count)`; one deterministic row per component.
* `incident_events(incident_id, event_id, position, source_sequence, is_survivor)`; complete membership in canonical order.
* `transitions(incident_id, transition_no, event_id, occurred_at, from_state, policy_version, to_state, actor, details)`; only state changes of surviving events.
* `sla_windows(incident_id, window_no, starts_at, ends_at, policy_version, target_seconds, elapsed_seconds, breached)`; deterministic segments evaluated against effective policies.
* `replay_audit(audit_id, run_id, incident_id, event_count, input_fingerprint, output_fingerprint, warnings, created_at)`; deterministic audit evidence.

The destination is replaced only after successful completion. Replaying the same input is deterministic and insertion-order independent.
