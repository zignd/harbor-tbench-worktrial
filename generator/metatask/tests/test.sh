#!/bin/bash
# Meta-task verifier: reward 1 if /app/output holds a structurally complete task
# package. Functional checks (docker build, oracle, nop) run later on the host.
python3 /tests/check_package.py /app/output > /logs/verifier/package-check.txt 2>&1
if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
cat /logs/verifier/package-check.txt
