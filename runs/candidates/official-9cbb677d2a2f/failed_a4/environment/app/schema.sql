CREATE TABLE archival_events(source_id INTEGER PRIMARY KEY, source TEXT, source_seq INTEGER, occurred_at TEXT, original_actor TEXT, resolved_actor TEXT, correlation TEXT, event_type TEXT, payload TEXT, depends_on TEXT, correction_of TEXT, supersedes TEXT);
CREATE TABLE incidents(incident_id TEXT PRIMARY KEY, correlation TEXT, opened_at TEXT, resolved_at TEXT, final_state TEXT);
CREATE TABLE incident_events(incident_id TEXT, source_id INTEGER, ordinal INTEGER, PRIMARY KEY(incident_id,source_id));
CREATE TABLE transitions(incident_id TEXT, ordinal INTEGER, source_id INTEGER, state TEXT, actor TEXT, policy_version TEXT, occurred_at TEXT, PRIMARY KEY(incident_id,ordinal));
CREATE TABLE sla_windows(incident_id TEXT, source_id INTEGER, policy_version TEXT, start_at TEXT, end_at TEXT, PRIMARY KEY(incident_id,source_id));
CREATE TABLE replay_audit(incident_id TEXT PRIMARY KEY, event_count INTEGER, digest TEXT);
