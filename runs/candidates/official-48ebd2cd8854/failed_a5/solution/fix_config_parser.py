#!/usr/bin/env python3
"""Fix config_parser.c: replace buggy config_get with correct strcmp-based version."""
import sys, re

path = sys.argv[1] if len(sys.argv) > 1 else '/app/service/config_parser.c'
with open(path) as f:
    src = f.read()

# The corrected function uses strcmp for exact key matching
correct = (
    'double config_get(const ConfigStore *store, const char *key) {\n'
    '    int i;\n'
    '    if (!store || !key) return 0.0;\n'
    '    for (i = 0; i < store->count; i++) {\n'
    '        if (strcmp(store->entries[i].key, key) == 0) {\n'
    '            return store->entries[i].value;\n'
    '        }\n'
    '    }\n'
    '    fprintf(stderr, "config_parser: key \'%s\' not found\\n", key);\n'
    '    return 0.0;\n'
    '}'
)

pat = re.compile(
    r'double config_get\(const ConfigStore \*store, const char \*key\)\s*\{.*?^\}',
    re.DOTALL | re.MULTILINE
)
m = pat.search(src)
if not m:
    print('ERROR: config_get function not found in', path, file=sys.stderr)
    sys.exit(1)

src = src[:m.start()] + correct + src[m.end():]
with open(path, 'w') as f:
    f.write(src)
print('Fix 1 applied: config_get now uses strcmp for exact key matching')
