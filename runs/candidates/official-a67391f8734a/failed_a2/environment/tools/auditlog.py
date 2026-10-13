"""Small stderr-only logging helper for the modal audit service."""
import datetime
import os
import sys

_LEVELS = {'debug': 10, 'info': 20, 'warning': 30, 'error': 40}

def _threshold():
    value = os.environ.get('MODAL_AUDIT_LOG_LEVEL', 'warning').lower()
    return _LEVELS.get(value, 30)

def write(level, message, **fields):
    if _LEVELS.get(level, 30) < _threshold():
        return
    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    suffix = ''.join(' %s=%r' % (key, fields[key]) for key in sorted(fields))
    sys.stderr.write('[%s] %s %s%s\n' % (stamp, level, message, suffix))
    sys.stderr.flush()

def debug(message, **fields): write('debug', message, **fields)
def info(message, **fields): write('info', message, **fields)
def warning(message, **fields): write('warning', message, **fields)
def error(message, **fields): write('error', message, **fields)

class Counter:
    def __init__(self): self.values = {}
    def add(self, name, amount=1): self.values[name] = self.values.get(name, 0) + amount
    def snapshot(self): return dict(self.values)
    def report(self):
        for name in sorted(self.values): debug('counter', name=name, value=self.values[name])
