CREATE VIEW normalized_events AS SELECT stream,seq,modality,ts,status,duration,trace FROM events;
