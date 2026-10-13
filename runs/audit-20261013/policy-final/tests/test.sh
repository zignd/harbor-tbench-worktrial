#!/bin/sh
# Offline verifier: the pinned uv and its pytest/py3.13 cache are baked into the image at build
# time, so verification needs no network. pytest runs in an isolated uv-managed interpreter.
set -u
mkdir -p /logs/verifier
cd /tests
UV_CACHE_DIR=/opt/uv-cache uvx --offline --from pytest==8.4.1 pytest /tests/test_outputs.py -q
rc=$?
if [ "$rc" -eq 0 ]; then echo 1 > /logs/verifier/reward.txt; else echo 0 > /logs/verifier/reward.txt; fi
exit "$rc"
