import sys
sys.path.insert(0,'/opt/ledgerforge')
from tools.rfx import make
open('/opt/ledgerforge/data/clean.rfx','wb').write(make([(0,7,0),(1,2,-1),(2,0,0)]))
open('/opt/ledgerforge/data/bad-day.rfx','wb').write(make([(0,7,0),(1,2,-1),(2,9,0),(3,4,1)],damaged={1}))
