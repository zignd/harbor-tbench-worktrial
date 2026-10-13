#!/bin/bash
set -e
printf 'SQLITE_CORRUPT: database disk image is malformed\n' >&2
exit 1
