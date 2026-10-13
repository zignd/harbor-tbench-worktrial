#!/usr/bin/env python3
import sqlite3,sys

def describe(path):
    db=sqlite3.connect(path)
    for name,sql in db.execute("select name,sql from sqlite_master where type='table' order by name"):
        print(name, sql)
if __name__=='__main__': describe(sys.argv[1])
