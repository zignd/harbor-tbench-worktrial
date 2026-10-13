DEFAULTS={'listen_host':'0.0.0.0','listen_port':9100,'sink_host':'127.0.0.1','sink_port':9200,'batch_size':64,'flush_seconds':1.0}
def normalized(values=None):
    out=dict(DEFAULTS); out.update(values or {})
    out['listen_port']=int(out['listen_port']); out['sink_port']=int(out['sink_port'])
    out['batch_size']=max(1,int(out['batch_size']))
    return out
