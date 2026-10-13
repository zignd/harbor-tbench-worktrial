CREATE TABLE epochs(epoch INTEGER PRIMARY KEY, prime TEXT NOT NULL, threshold INTEGER NOT NULL, share_count INTEGER NOT NULL, commitment TEXT NOT NULL, anchor_digest TEXT NOT NULL);
CREATE TABLE key_shares(epoch INTEGER, share_id INTEGER, x INTEGER, y TEXT, PRIMARY KEY(epoch,share_id));
CREATE TABLE accounts(account TEXT PRIMARY KEY, label TEXT);
CREATE TABLE audit_events(event_id TEXT PRIMARY KEY, epoch INTEGER, sequence INTEGER, account TEXT, predecessor TEXT, payload TEXT, mac TEXT);
CREATE TABLE chain_anchors(epoch INTEGER PRIMARY KEY, digest TEXT NOT NULL);
CREATE TABLE terminal_checkpoints(epoch INTEGER, sequence INTEGER, digest TEXT, signature TEXT, PRIMARY KEY(epoch,sequence));
CREATE TABLE incident_metadata(name TEXT PRIMARY KEY, value TEXT);
