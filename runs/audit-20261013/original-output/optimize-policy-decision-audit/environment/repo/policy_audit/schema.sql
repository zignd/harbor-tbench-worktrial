PRAGMA foreign_keys=ON;
CREATE TABLE tenants(tenant_id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
CREATE TABLE policy_definitions(policy_id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL REFERENCES tenants, resource_prefix TEXT NOT NULL, action TEXT NOT NULL, effect TEXT NOT NULL, priority INTEGER NOT NULL, reason TEXT NOT NULL);
CREATE TABLE policy_revisions(revision_id INTEGER PRIMARY KEY, policy_id INTEGER NOT NULL REFERENCES policy_definitions, revision_ts INTEGER NOT NULL, revision_seq INTEGER NOT NULL);
CREATE TABLE policy_bindings(binding_id INTEGER PRIMARY KEY, policy_id INTEGER NOT NULL REFERENCES policy_definitions, revision_id INTEGER NOT NULL REFERENCES policy_revisions);
CREATE TABLE access_requests(request_sequence INTEGER PRIMARY KEY, request_id TEXT NOT NULL, tenant_id INTEGER NOT NULL REFERENCES tenants, resource TEXT NOT NULL, action TEXT NOT NULL, event_ts INTEGER NOT NULL);
