Finish and deploy the replay utility in /opt/replayd. The installed executable /usr/local/bin/db-replay must work from any working directory and support db-replay --config PATH, db-replay --input DIR --output PATH, and db-replay --check.

Read the format manual and manifest rather than assuming fixture names. Recursively process every manifest-selected event file, including records and transactions split across files. Parse quoted tabs, quotes, Unicode, and embedded newlines correctly. A transaction contributes only when it has a valid commit, valid structure, and matching checksum; aborted, incomplete, malformed, and invalid-checksum transactions contribute nothing. Apply committed transactions by commit LSN, then operation sequence, and apply a transaction appearing in multiple shards only once.

Emit exactly one compact canonical JSON object per live row using the documented fields and ordering, sorted by table and primary key. Emit a deterministic report containing input_records, committed_transactions, ignored_transactions, live_rows, and the SHA-256 of the canonical JSONL bytes. A delete of a missing key, delete of an existing key, and upsert of an existing key must retain their documented semantics.

Publish snapshot and report together atomically. A failed replay must leave existing outputs untouched. --check must validate the installed deployment, configuration, manifest, input selection, and output checksum without modifying any input or output.

The implementation must remain accurate on large bundles with shuffled files, duplicate deliveries, malformed records, cross-file transactions, out-of-order commits, and escaped multiline fields, and must process at least 25,000 physical records per second on the verifier corpus.
