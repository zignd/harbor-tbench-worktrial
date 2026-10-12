#!/usr/bin/env python3
"""Fix db_writer.c: remove weight truncation in db_write_weight_cache."""
import sys, re

path = sys.argv[1] if len(sys.argv) > 1 else '/app/service/db_writer.c'
with open(path) as f:
    src = f.read()

orig = src

# Remove the comment about short decimal string storage
src = re.sub(r'[ \t]*/\* Format weight as a short decimal string for storage \*/\n', '', src)
# Remove the snprintf truncation line
src = re.sub(r'[ \t]*snprintf\(valbuf,[ \t]*6,[ \t]*"%.2f",[ \t]*w\);[ \t]*\n', '', src)
# Replace atof(valbuf) with w directly
src = re.sub(r'sqlite3_bind_double\(stmt,[ \t]*2,[ \t]*atof\(valbuf\)\)',
             'sqlite3_bind_double(stmt, 2, w)', src)

if src == orig:
    print('WARNING: no changes made to', path, file=sys.stderr)
else:
    with open(path, 'w') as f:
        f.write(src)
    print('Fix 2 applied: weight stored with full double precision')
