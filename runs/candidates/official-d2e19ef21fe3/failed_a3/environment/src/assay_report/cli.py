import sys,json
from .pipeline import report

def main(argv=None):
    argv=sys.argv[1:] if argv is None else argv
    if len(argv)!=2: raise SystemExit('usage: python -m assay_report DATABASE OUTPUT.JSON')
    data=report(argv[0])
    with open(argv[1],'w',encoding='utf-8',newline='\n') as f:
        f.write(json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n')
