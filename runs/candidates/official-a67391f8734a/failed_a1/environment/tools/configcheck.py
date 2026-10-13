#!/usr/bin/env python3
"""Configuration checks used by the service maintenance utility."""
import argparse
import pathlib

REQUIRED = {'service', 'mode', 'max_dimension'}
ALLOWED_MODES = {'stream'}

def read_config(path):
    result = {}
    for number, raw in enumerate(pathlib.Path(path).read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            raise ValueError('line %d lacks an assignment' % number)
        key, value = (part.strip() for part in line.split('=', 1))
        if not key or key in result:
            raise ValueError('invalid key on line %d' % number)
        result[key] = value
    return result

def validate(values):
    missing = REQUIRED - set(values)
    if missing:
        raise ValueError('missing: ' + ','.join(sorted(missing)))
    if values['service'] != 'modal-audit':
        raise ValueError('unexpected service')
    if values['mode'] not in ALLOWED_MODES:
        raise ValueError('unexpected mode')
    try: dimension = int(values['max_dimension'])
    except ValueError as exc: raise ValueError('dimension is not numeric') from exc
    if not 1 <= dimension <= 12:
        raise ValueError('dimension out of range')
    return dimension

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('path')
    args = parser.parse_args(argv)
    values = read_config(args.path)
    validate(values)
    print('valid')
    return 0

if __name__ == '__main__': raise SystemExit(main())
