import sqlite3

def get_target_shard_naive(resource_id):
    return sum(ord(c) for c in resource_id) % 256

conn = sqlite3.connect('infra.db')
conn.create_function("get_target_shard", 1, get_target_shard_naive)
conn.execute("CREATE TABLE metadata (id TEXT PRIMARY KEY, data TEXT, shard_id INTEGER)")
conn.execute("INSERT INTO metadata (id, data) VALUES ('web-01', 'prod server'), ('db-01', 'primary db')")
conn.commit()
conn.close()
