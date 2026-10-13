"""Read-only catalog access helpers used by catalog inspection tools."""
import sqlite3

def connect(path):
    con=sqlite3.connect(path)
    con.row_factory=sqlite3.Row
    return con

def table_names(con):
    return tuple(r[0] for r in con.execute("select name from sqlite_master where type='table' order by name"))

def rows(con, table, columns='*'):
    allowed={'runs','measurements','controls','cohorts','unit_factors','export_fragments'}
    if table not in allowed: raise ValueError(table)
    return con.execute('select '+columns+' from '+table)

def catalog_summary(path):
    con=connect(path)
    try:return {t:con.execute('select count(*) from '+t).fetchone()[0] for t in table_names(con)}
    finally:con.close()
