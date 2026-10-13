import sys

data=sys.stdin.buffer.read()
if data[:4] != b'MAF2':
    sys.stderr.write('no initial frame\n')
    raise SystemExit(0)
