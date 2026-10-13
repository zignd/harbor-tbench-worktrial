def instrument_health(events):
    result={}
    for event in events:
        name=event.get('instrument','unknown')
        result[name]=result.get(name,0)+1
    return {'instruments':result,'total':sum(result.values())}
