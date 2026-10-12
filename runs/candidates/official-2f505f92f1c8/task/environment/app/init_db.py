import sqlite3

db = sqlite3.connect('/app/var/audit.db')
c = db.cursor()

c.executemany(
    'INSERT INTO wal_records (txid, record_type, payload) VALUES (?,?,?)',
    [
        (1001, 'charge', bytes.fromhex('deadbeef01')),
        (1002, 'charge', bytes.fromhex('deadbeef02')),
        (5001, 'charge', bytes.fromhex('cafebabe01')),
        (5002, 'charge', bytes.fromhex('cafebabe02')),
        (9999999, 'charge', bytes.fromhex('aabbcc9999')),
        (7777,    'charge', bytes.fromhex('11223344')),
        (8888,    'charge', bytes.fromhex('55667788')),
    ]
)

c.executemany(
    'INSERT INTO charges (txid, amount, ts) VALUES (?,?,?)',
    [
        (1001,    4999,  1700000001),
        (1002,    9999,  1700000002),
        (5001,    1500,  1700005001),
        (5002,    2500,  1700005002),
        (9999999, 29900, 1700009999),
        (7777,    3750,  1700007777),
        (8888,    8000,  1700008888),
    ]
)

c.executemany(
    'INSERT INTO wal_records (txid, record_type, payload) VALUES (?,?,?)',
    [
        (2001,    'refund', bytes.fromhex('f00d2001')),
        (2002,    'refund', bytes.fromhex('f00d2002')),
        (3042,    'refund', bytes.fromhex('f00d3042')),
        (8000042, 'refund', bytes.fromhex('f00d8042')),
    ]
)

c.executemany(
    'INSERT INTO refund_refs (refund_txid, charge_txid) VALUES (?,?)',
    [
        (2001,    1001),
        (2002,    1002),
        (3042,    5001),
        (8000042, 9999999),
    ]
)

db.commit()
db.close()
