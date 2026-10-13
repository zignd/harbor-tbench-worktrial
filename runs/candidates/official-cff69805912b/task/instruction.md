Your team runs a small audit-log service at /app/audit_service/. Application nodes write structured log files to /app/logs/, where each entry must carry a valid HMAC-SHA256 chaining signature. The HMAC key for entry N is derived from the HMAC tag of entry N-1; the genesis entry (index 0) uses the fixed seed from /app/config/chain.cfg (field 'seed', hex-encoded). See /app/tools/chain_spec.md for the full algorithm.

A compliance checker connects over a simple line-oriented protocol on stdin/stdout. It sends:

  VERIFY <logfile>

and expects OK <entry_count> if the entire HMAC chain from the genesis entry to the last entry is intact, or FAIL <first_bad_entry_index> (0-indexed) if any entry has an invalid HMAC. It also sends:

  QUERY <logfile> <entry_index>

and expects the raw payload string of that entry on a single line, or NOTFOUND if the index is out of range or the file does not exist. The service exits when stdin is closed.

The service currently gives wrong answers on some log files. Fix /app/audit_service/ so that it answers all protocol requests correctly. Requirements:

- VERIFY must return OK <entry_count> when every HMAC chain link is valid from the genesis entry to the last entry.
- VERIFY must return FAIL <first_bad_entry_index> (0-indexed) when any entry has an invalid HMAC; the index refers to the data entry index (not counting the header line).
- QUERY must return the exact raw payload string of the requested entry. Payloads may contain the literal two-character sequence \n (backslash followed by n); these must be returned exactly as stored, not converted to real newlines.
- QUERY must return NOTFOUND if the index is out of range or the file does not exist.
- The HMAC key for entry N (N > 0) is HMAC-SHA256(key=<ASCII bytes of the 64-char hex tag of entry N-1>, msg=b'key'). The genesis entry uses the raw bytes of the hex-decoded seed.
- The service must handle log files with up to 10000 entries correctly and respond to a VERIFY request on a 1000-entry log within 5 seconds.
- A tampered payload (HMAC tag unchanged) and a tampered HMAC tag (payload unchanged) must both be detected and reported as FAIL.
- Do not modify any files in /app/logs/ or /app/config/.

The entry point is /app/audit_service/service.py. Log files in VERIFY and QUERY commands are resolved as absolute paths if they start with /, otherwise relative to /app/logs/.
