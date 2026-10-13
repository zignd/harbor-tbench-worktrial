"""Non-report plotting data helpers."""
def bounds(values):
    values=tuple(values)
    return (min(values),max(values)) if values else (None,None)
def normalize(values):
    values=tuple(values); lo,hi=bounds(values)
    if lo is None:return ()
    if hi==lo:return tuple(0.0 for _ in values)
    return tuple((x-lo)/(hi-lo) for x in values)
def bins(values, count=10):
    if count<1:raise ValueError('count')
    return tuple(int(min(count-1,max(0,x*count))) for x in normalize(values))
