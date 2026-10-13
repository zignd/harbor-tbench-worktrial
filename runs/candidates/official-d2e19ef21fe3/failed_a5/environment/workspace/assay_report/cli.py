import sys
from .report import make_report

def main():
 if len(sys.argv)!=3: raise SystemExit('usage: python -m assay_report DATABASE OUTPUT')
 make_report(sys.argv[1],sys.argv[2])
