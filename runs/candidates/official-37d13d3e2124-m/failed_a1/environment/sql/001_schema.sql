CREATE TABLE IF NOT EXISTS raw(event_id TEXT,ts_ms INTEGER,tenant TEXT,session TEXT,op TEXT,latency_us INTEGER,status TEXT,relative_filename TEXT,physical_line INTEGER);
CREATE TABLE IF NOT EXISTS sessions(tenant TEXT,session TEXT,start_ms INTEGER,finish_ms INTEGER,event_count INTEGER,error_count INTEGER,duration_ms INTEGER);
