#!/usr/bin/env python3
"""Small operational report utility retained with the deployment artifacts."""
import json, os, pathlib, time

def snapshot(root='/var/run/relay'):
    result={'root':root,'pidfiles':{}}
    for p in pathlib.Path(root).glob('*.pid'):
        try: result['pidfiles'][p.name]=int(p.read_text().strip())
        except (ValueError,OSError): result['pidfiles'][p.name]=None
    return result

def render(data):
    return json.dumps(data,sort_keys=True,separators=(',',':'))

if __name__=='__main__': print(render(snapshot()))
