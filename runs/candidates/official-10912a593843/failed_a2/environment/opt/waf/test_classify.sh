#!/bin/bash
# Test harness: loop over /opt/waf/samples/ and print PASS/FAIL per sample.
# Each sample JSON has a "label" field: "malicious" or "benign".
# malicious => filter must exit 1 (blocked)
# benign    => filter must exit 0 (allowed)

SAMPLES_DIR="${1:-/opt/waf/samples}"
PASS=0
FAIL=0
ERRORS=0

for sample in "$SAMPLES_DIR"/*.json; do
    label=$(python3 -c "import json,sys; d=json.load(open('$sample')); print(d.get('label',''))" 2>/dev/null)
    if [ -z "$label" ]; then
        echo "ERROR: no label in $sample"
        ((ERRORS++))
        continue
    fi

    python3 /opt/waf/filter/classify.py "$sample" >/dev/null 2>&1
    exit_code=$?

    if [ "$label" = "malicious" ]; then
        expected=1
    elif [ "$label" = "benign" ]; then
        expected=0
    else
        echo "ERROR: unknown label '$label' in $sample"
        ((ERRORS++))
        continue
    fi

    fname=$(basename "$sample")
    if [ "$exit_code" -eq "$expected" ]; then
        echo "PASS [$label] $fname"
        ((PASS++))
    else
        echo "FAIL [$label] $fname (exit=$exit_code expected=$expected)"
        ((FAIL++))
    fi
done

echo ""
echo "Results: PASS=$PASS FAIL=$FAIL ERRORS=$ERRORS"
if [ "$FAIL" -gt 0 ] || [ "$ERRORS" -gt 0 ]; then
    exit 1
fi
