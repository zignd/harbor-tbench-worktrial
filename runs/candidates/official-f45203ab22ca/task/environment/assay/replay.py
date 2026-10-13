import json
def parse(lines):
    return [json.loads(line) for line in lines if line.strip()]
