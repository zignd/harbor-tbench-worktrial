#!/bin/bash
set -eE
trap 'pkill -9 -f sqlite3; rm -f /dev/shm/*quant*' ERR
sed -n '/^---END-HEADER---$/,$p' "$1" | /opt/quant-reconcile/bin/stat_accumulator
