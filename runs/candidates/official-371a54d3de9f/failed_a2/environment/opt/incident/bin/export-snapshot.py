#!/usr/bin/env python3
import csv,sqlite3,sys,os

def main(db,directory):
    os.makedirs(directory,exist_ok=True); con=sqlite3.connect(db)
    tables={'epochs':['epoch','prime','threshold','commitment'],'shares':['epoch','x','y'],'events':['event_id','account','epoch','sequence','predecessor','payload','mac'],'anchors':['epoch','event_id'],'checkpoints':['epoch','sequence','event_id','signature'],'accounts':['account','description'],'incident_metadata':['name','value']}
    for table,cols in tables.items():
        with open(os.path.join(directory,table+'.csv'),'w',newline='',encoding='utf8') as f:
            w=csv.writer(f); w.writerow(cols); w.writerows(con.execute('select '+','.join(cols)+' from '+table))
if __name__=='__main__': main(sys.argv[1],sys.argv[2])
