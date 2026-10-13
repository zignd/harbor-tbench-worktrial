PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
CREATE TABLE IF NOT EXISTS batch_reconcile(batch_id TEXT PRIMARY KEY,worker_node TEXT,record_count INTEGER,mean_drift REAL,var_surface REAL,status TEXT,spool_checksum TEXT);
CREATE TABLE IF NOT EXISTS anomaly_records(batch_id TEXT,trade_id TEXT,drift REAL,variance REAL,reason TEXT,PRIMARY KEY(batch_id,trade_id,reason));
CREATE TABLE IF NOT EXISTS worker_audit(worker_node TEXT PRIMARY KEY,batch_count INTEGER,record_count INTEGER,spool_checksums TEXT);
