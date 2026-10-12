#!/usr/bin/env bash
set -uo pipefail
mkdir -p /logs/verifier
if uvx --from pytest pytest /tests/test_outputs.py -v 2>&1 | tee /logs/verifier/pytest.log; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
