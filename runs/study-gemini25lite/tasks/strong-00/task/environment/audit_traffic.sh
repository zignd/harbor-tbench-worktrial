#!/bin/bash
# Audit script to check rate limiter compliance and performance.

cd "$(dirname "$0")"

export RATE=1000
export CAPACITY=100
export CGO_ENABLED=0

# Start the server in the background
go run main.go &
SERVER_PID=$!

# Ensure we kill the server on exit
trap "kill $SERVER_PID" EXIT

sleep 2

# Run traffic generator
DURATION=5
EXPECTED=$(python3 -c "print($RATE * $DURATION + $CAPACITY)")

echo "Running audit..."
RESULT=$(/usr/bin/traffic-gen -url http://localhost:8080 -duration ${DURATION}s -concurrent 100)
echo "$RESULT"

OK_COUNT=$(echo "$RESULT" | grep -oP "OK: \K\d+")

MARGIN=0.05
LOWER_BOUND=$(python3 -c "print(int($EXPECTED * (1 - $MARGIN)))")
UPPER_BOUND=$(python3 -c "print(int($EXPECTED * (1 + $MARGIN)))")

if [ "$OK_COUNT" -lt "$LOWER_BOUND" ] || [ "$OK_COUNT" -gt "$UPPER_BOUND" ]; then
    echo "Audit FAILED: OK count $OK_COUNT out of expected $EXPECTED range [$LOWER_BOUND, $UPPER_BOUND]"
    exit 1
fi

echo "Audit PASSED"
exit 0
