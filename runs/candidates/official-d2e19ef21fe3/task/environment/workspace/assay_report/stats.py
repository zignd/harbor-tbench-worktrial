import statistics
def quantile(a,p):
    if not a:return None
    x=sorted(a); z=(len(x)-1)*p; lo=int(z); hi=min(lo+1,len(x)-1); return x[lo]+(x[hi]-x[lo])*(z-lo)
def tukey(a):
    if len(a)<2:return list(a)
    q1,q3=quantile(a,.25),quantile(a,.75); f=1.5*(q3-q1)
    return [x for x in a if q1-f<=x<=q3+f]
def med(a):return statistics.median(a) if a else None
