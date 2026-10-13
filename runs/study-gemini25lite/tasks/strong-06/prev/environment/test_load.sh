#!/bin/bash
# Shallow check: only 1000 RPS
for i in {1..1000}; do
  echo "log message $i" | nc -u -w0 127.0.0.1 8888
  sleep 0.001
done
