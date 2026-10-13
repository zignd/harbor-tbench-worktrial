import argparse,json
from repository import latest
from reconcile import build_report

def main():
 p=argparse.ArgumentParser(); p.add_argument('--db',required=True); p.add_argument('--out',required=True); p.add_argument('--window-ns',required=True,type=int); a=p.parse_args()
 report=build_report(latest(a.db,'ledger_events'),latest(a.db,'bank_events'),a.window_ns)
 with open(a.out,'w',encoding='utf-8',newline='') as f: json.dump(report,f,ensure_ascii=False,separators=(',',':'),sort_keys=True); f.write('\n')
 with open('/opt/settlement-recon/var/last.json','w',encoding='utf-8') as f: json.dump(report,f,ensure_ascii=False,separators=(',',':'),sort_keys=True)

if __name__ == '__main__':
 main()
