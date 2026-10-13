# Audit Log HMAC Chain Service

## Overview

This service maintains tamper-evident audit logs for application nodes in a
constrained DevOps environment. Each log file is a chain of HMAC-signed
entries; the HMAC key for each entry is derived from the previous entry's tag,
forming an unforgeable sequence.

## Repository Layout

```
/app/
  audit_service/         Service package
    __init__.py
    chain.so             Compiled HMAC derivation module (Cython)
    parser.py            Log file parser
    service.py           Protocol entry point (stdin/stdout)
    verifier.py          Chain verifier, calls chain.so
  config/
    chain.cfg            INI config: genesis seed for HMAC chain
  logs/                  Pre-generated log files from application nodes
  tools/
    chain_spec.md        Authoritative chain algorithm specification
    generate_logs.py     Deterministic log generator (for testing/reference)
```

## Running the Service

```
python3 -m audit_service.service
```

Or directly:

```
python3 /app/audit_service/service.py
```

The service reads from stdin and writes to stdout. Log files may be referenced
by absolute path or by filename (resolved relative to `/app/logs/`).

## Protocol

```
VERIFY <logfile>
OK <entry_count>

VERIFY <logfile>
FAIL <first_bad_index>

QUERY <logfile> <index>
<payload>

QUERY <logfile> <index>
NOTFOUND

```

## Log Format

See `/app/tools/chain_spec.md` for the complete format and algorithm
specification.

## Configuration

`/app/config/chain.cfg` contains the genesis seed:

```ini
[chain]
seed = <32-byte hex string>
```

## Dependencies

- Python 3.13
- `cryptography` package
- `configparser` (stdlib)

## History

Version 1.4.2 ships with a compiled verifier module (`chain.so`) built from
Cython source. The module provides the `verify_chain_entry` function used by
`verifier.py` to check each entry's HMAC tag.

The compliance checker began reporting failures in build 1.4.0. Logs that the
service marks as valid are being rejected by the compliance checker.

## Quick Test

```bash
echo 'VERIFY /app/logs/valid_10.log' | python3 /app/audit_service/service.py
echo 'QUERY /app/logs/valid_10.log 0' | python3 /app/audit_service/service.py
```
