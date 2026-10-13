CREATE TABLE events(stream TEXT,seq INTEGER,modality TEXT,ts INTEGER,status INTEGER,duration INTEGER,trace INTEGER,shard TEXT);
CREATE INDEX events_key ON events(stream,seq);
