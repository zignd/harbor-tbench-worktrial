-- schema.sql - audit database schema
-- Creates tables used by the WAL audit service.

CREATE TABLE IF NOT EXISTS wal_records (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    txid        INTEGER NOT NULL,
    record_type TEXT    NOT NULL,
    payload     BLOB
);

CREATE INDEX IF NOT EXISTS idx_wal_records_txid ON wal_records(txid);

-- charges: records of charge transactions
CREATE TABLE IF NOT EXISTS charges (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    txid   INTEGER NOT NULL UNIQUE,
    amount INTEGER NOT NULL,
    ts     INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_charges_txid ON charges(txid);

-- refund_refs: maps each refund transaction to the charge it reverses
-- refund_txid: the txid of the refund WAL record
-- charge_txid: the txid of the charge being reversed
CREATE TABLE IF NOT EXISTS refund_refs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    refund_txid INTEGER NOT NULL UNIQUE,
    charge_txid INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_refund_refs_rtxid ON refund_refs(refund_txid);
