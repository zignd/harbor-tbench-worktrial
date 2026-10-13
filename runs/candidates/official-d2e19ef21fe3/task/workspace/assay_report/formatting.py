"""Deterministic JSON formatting utilities."""
import json, math

def finite_or_none(value):
    if value is None:return None
    return value if math.isfinite(float(value)) else None

def normalize_row(row):
    return {k:(finite_or_none(v) if isinstance(v,(int,float)) else v) for k,v in row.items()}

def encode(rows):
    clean=[[normalize_row(r) for r in rows]][0]
    return json.dumps(clean,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n'

def write(path, rows):
    with open(path,'w',encoding='utf-8',newline='\n') as f:f.write(encode(rows))
