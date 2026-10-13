import sqlite3

def connect(path):
    c=sqlite3.connect('file:'+path+'?mode=ro',uri=True)
    c.row_factory=sqlite3.Row
    return c

def rows(c,table): return [dict(x) for x in c.execute('select * from '+table)]
