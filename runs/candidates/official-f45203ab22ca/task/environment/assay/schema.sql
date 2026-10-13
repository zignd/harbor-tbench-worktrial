CREATE TABLE events(event_id TEXT PRIMARY KEY, assay TEXT NOT NULL, sample_id TEXT NOT NULL, instrument TEXT NOT NULL, observed_at TEXT NOT NULL, delivered_at TEXT NOT NULL, x REAL NOT NULL, y REAL NOT NULL, stderr REAL NOT NULL, supersedes TEXT);
CREATE INDEX events_assay_delivery ON events(assay, delivered_at);
