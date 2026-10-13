import sqlite3

def latest(db, table):
    con=sqlite3.connect(db)
    con.row_factory=sqlite3.Row
    q=f'''SELECT record_id,version,state,account,currency,amount,event_ns FROM
          (SELECT *, ROW_NUMBER() OVER (PARTITION BY record_id ORDER BY version DESC) rn FROM {table})
          WHERE rn=1 AND state='posted' ORDER BY record_id'''
    rows=[dict(x) for x in con.execute(q)]
    con.close()
    return rows
