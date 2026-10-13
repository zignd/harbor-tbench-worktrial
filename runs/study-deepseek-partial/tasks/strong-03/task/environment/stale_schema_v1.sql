-- Schema v1 (deprecated 2024-03)
-- This was the original table structure before query_id became the primary key.
-- Kept for reference during migration troubleshooting.

CREATE TABLE IF NOT EXISTS query_loads_v1 (
    row_id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_identifier INTEGER NOT NULL,
    load_value INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    shard_assignment INTEGER DEFAULT -1
);

CREATE INDEX IF NOT EXISTS idx_query_identifier ON query_loads_v1(query_identifier);
CREATE INDEX IF NOT EXISTS idx_created ON query_loads_v1(created_at);

-- Note: This schema was abandoned because row_id-based joins caused
-- performance issues with the dispatch loop. The v2 schema uses
-- a simpler (query_id, load, timestamp) tuple without auto-increment.
