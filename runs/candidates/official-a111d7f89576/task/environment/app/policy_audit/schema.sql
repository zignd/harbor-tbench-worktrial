CREATE TABLE tenants(tenant_id INTEGER PRIMARY KEY,name TEXT);
CREATE TABLE policies(policy_id INTEGER PRIMARY KEY,tenant_id INTEGER,resource_prefix TEXT,action TEXT,effect TEXT,priority INTEGER);
CREATE TABLE policy_revisions(revision_id INTEGER PRIMARY KEY,policy_id INTEGER,revision_timestamp INTEGER,revision_sequence INTEGER);
CREATE TABLE policy_bindings(binding_id INTEGER PRIMARY KEY,revision_id INTEGER,valid_from INTEGER,valid_until INTEGER);
CREATE TABLE access_requests(request_row_id INTEGER PRIMARY KEY,request_id TEXT,ingestion_sequence INTEGER,tenant_id INTEGER,resource TEXT,action TEXT,requested_at INTEGER);
CREATE INDEX requests_seq ON access_requests(ingestion_sequence);
CREATE INDEX policies_match ON policies(tenant_id,action);
CREATE INDEX revisions_policy ON policy_revisions(policy_id,revision_timestamp,revision_sequence);
CREATE INDEX bindings_revision ON policy_bindings(revision_id,valid_from,valid_until);
