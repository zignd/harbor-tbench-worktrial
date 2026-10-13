CREATE TABLE IF NOT EXISTS queries (
    query_id INTEGER PRIMARY KEY,
    load INTEGER NOT NULL,
    timestamp INTEGER NOT NULL
);

DELETE FROM queries;

.import /app/sample_data.csv queries --csv --skip 1
