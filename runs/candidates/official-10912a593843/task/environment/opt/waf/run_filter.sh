#!/bin/bash
# Invoke the WAF classifier on a request JSON file.
# Usage: run_filter.sh <request_json_file>
# Exit code: 0 = allowed (benign), 1 = blocked (malicious), 2 = error
exec python3 /opt/waf/filter/classify.py "$1"
