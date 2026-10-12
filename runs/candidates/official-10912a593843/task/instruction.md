The WAF at /opt/waf is deployed but misclassifying requests: some malicious requests reach the backend and some legitimate requests are blocked. Fix the compiler, deployment pipeline, and runtime filter so every request in /opt/waf/samples/ is classified correctly according to its label, and the rule version recorded in /opt/waf/state.db matches the compiled rule set actually loaded by the filter.

The filter is invoked via /opt/waf/run_filter.sh <request_json_file>, which exits 0 for allowed (benign) requests and 1 for blocked (malicious) requests.

Requirements:
- Every request in /opt/waf/samples/ with label "malicious" must be rejected by the filter (exit 1).
- Every request in /opt/waf/samples/ with label "benign" must be allowed by the filter (exit 0).
- The value stored in /opt/waf/state.db under key "deployed" in table rule_state must equal the SHA-256 hex digest of the concatenated binary contents of all files in /opt/waf/deployed/, sorted by filename.
- The deployment script must update both the deployed rule files and the state.db version entry atomically: either both succeed or neither takes effect.
- The filter must produce the same classification for a given request on every invocation, regardless of any in-process state from previous invocations.
- When a request matches both an allow-list rule and a block rule, the block rule must win.
