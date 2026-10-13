from pathlib import Path
T='\t'
base=Path('/var/lib/flowwatch/spool'); base.mkdir(parents=True,exist_ok=True)
def row(c,t,p,s,d,sp,dp,e,q,n,r,f='-'):
 return T.join(map(str,[c,t,p,s,d,sp,dp,e,q,n,r,f]))
a=[row('a',100,'TCP','10.0.0.1','10.0.0.2',1000,443,7,4294967294,120,'red'),row('a',101,'TCP','10.0.0.1','10.0.0.2',1000,443,7,4294967295,80,'red'),row('a',102,'TCP','10.0.0.1','10.0.0.2',1000,443,7,0,100,'red,blue'),row('a',103,'TCP','10.0.0.1','10.0.0.2',1000,443,7,1,60,'blue'),row('b',110,'UDP','10.0.0.3','10.0.0.4',53,53000,2,10,40,'green')]
b=[row('b',200,'TCP','10.0.0.1','10.0.0.2',1000,443,7,4294967294,120,'red'),row('b',201,'TCP','10.0.0.1','10.0.0.2',1000,443,7,4294967295,80,'red'),row('b',202,'TCP','10.0.0.1','10.0.0.2',1000,443,7,0,100,'red,blue'),row('c',210,'UDP','10.0.0.3','10.0.0.4',53,53000,2,10,40,'green')]
(base/'collector-a.cap').write_text('\n'.join(a)+'\n'); (base/'collector-b.cap').write_text('\n'.join(b)+'\n')
