-- Operational stage query examples
SELECT event_id, min(ts_ms) FROM raw GROUP BY event_id;
SELECT tenant,session,count(*) FROM raw GROUP BY tenant,session;
