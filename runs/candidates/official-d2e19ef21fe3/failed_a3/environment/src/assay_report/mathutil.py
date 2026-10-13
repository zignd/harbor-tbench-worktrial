import math

def median(a):
    a=sorted(a)
    if not a:return None
    n=len(a); return (a[n//2] if n%2 else (a[n//2-1]+a[n//2])/2)
def quantile(a,p):
    a=sorted(a)
    if not a:return None
    x=p*(len(a)-1); lo=int(x); hi=min(lo+1,len(a)-1)
    return a[lo]+(a[hi]-a[lo])*(x-lo)
def tukey(a):
    if len(a)<2:return list(a)
    q1,q3=quantile(a,.25),quantile(a,.75); d=q3-q1
    return [x for x in a if q1-1.5*d <= x <= q3+1.5*d]
def finite(x): return x is not None and math.isfinite(x)
