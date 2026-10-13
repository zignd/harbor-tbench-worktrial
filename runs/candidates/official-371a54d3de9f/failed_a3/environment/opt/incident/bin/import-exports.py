#!/usr/bin/env python3
import csv,sqlite3,sys

def load(db,table,file,columns):
    con=sqlite3.connect(db)
    with open(file,newline='',encoding='utf8') as f:
        con.executemany('insert or ignore into '+table+'('+','.join(columns)+') values ('+','.join('?' for _ in columns)+')',csv.reader(f))
    con.commit()
if __name__=='__main__': load(sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4].split(','))
