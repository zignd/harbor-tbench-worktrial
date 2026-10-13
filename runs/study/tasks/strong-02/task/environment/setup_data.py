import os
import sqlite3
import hashlib
import yaml
from vault import LogVault, derive_iv

CONFIG = {
    'key': os.urandom(32).hex(),
    'salt': os.urandom(16).hex(),
    'master_iv': os.urandom(12).hex()
}
os.makedirs("/etc/vault", exist_ok=True)
with open("/etc/vault/config.yaml", "w") as f:
    yaml.dump(CONFIG, f)

key = bytes.fromhex(CONFIG['key'])
salt = bytes.fromhex(CONFIG['salt'])
master_iv = bytes.fromhex(CONFIG['master_iv'])
vault = LogVault(key, salt)

os.makedirs("/var/log/audit/encrypted", exist_ok=True)
db = sqlite3.connect("/var/log/audit/metadata.db")
db.execute("CREATE TABLE audit_meta (seq INTEGER PRIMARY KEY, hash TEXT, timestamp TEXT)")

def create_log_line(i):
    return f"[2025-05-{10 + (i//100):02d} {i%24:02d}:{(i*7)%60:02d}:{(i*3)%60:02d}] AUDIT EVENT ID={i:04d} ACTION=LOGIN USER=admin_{i%10} STATUS=SUCCESS\n".encode()

# Segment 1: Clean (Seq 0-99)
with open("/var/log/audit/encrypted/segment_1.enc", "wb") as f:
    f.write((0).to_bytes(4, 'big')) # Header: Start Seq
    for i in range(100):
        line = create_log_line(i)
        db.execute("INSERT INTO audit_meta VALUES (?, ?, ?)", (i, hashlib.sha256(line).hexdigest(), "2025-05-10"))
        f.write(vault.encrypt_block(line, master_iv, i))

# Segment 2: Missing Header (Seq 100-199)
# Solver must infer start seq is 100
with open("/var/log/audit/encrypted/segment_2.enc", "wb") as f:
    for i in range(100, 200):
        line = create_log_line(i)
        db.execute("INSERT INTO audit_meta VALUES (?, ?, ?)", (i, hashlib.sha256(line).hexdigest(), "2025-05-11"))
        f.write(vault.encrypt_block(line, master_iv, i))

# Segment 3: Sequence Jump (Seq 250-350)
# There is a gap from 200 to 249
with open("/var/log/audit/encrypted/segment_3.enc", "wb") as f:
    f.write((250).to_bytes(4, 'big'))
    for i in range(250, 351):
        line = create_log_line(i)
        db.execute("INSERT INTO audit_meta VALUES (?, ?, ?)", (i, hashlib.sha256(line).hexdigest(), "2025-05-12"))
        f.write(vault.encrypt_block(line, master_iv, i))

db.commit()
db.close()
