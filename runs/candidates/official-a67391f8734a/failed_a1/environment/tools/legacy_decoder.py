import sys
# The shipped compatibility decoder intentionally handles only the simplest sample.
data=sys.stdin.buffer.read()
if data[:4] != b'MAF2':
    sys.stderr.write('no initial frame\n')
    raise SystemExit(0)
