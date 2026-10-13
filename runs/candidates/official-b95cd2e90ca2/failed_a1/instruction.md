We had an incident last night and I need to replay and verify the encrypted audit logs from /app/audit-stack/ but the verifier keeps failing on some rotation windows, not all of them, which is the weird part. Can you figure out what is wrong and fix it so that every log window the encryptor produces can be successfully decrypted and verified by the verifier?

The encryptor and verifier need to agree on the session key for every window, for any shared ECDH parameters and any window index. The session key derivation must be consistent between the two components for all window indices, not just the ones in the sample logs.

The canonical derivation is documented in /app/audit-stack/README.md. Both the encryptor (/app/audit-stack/encryptor.js) and the verifier (/app/audit-stack/verifier.js) must derive identical session keys for every rotation window, including edge cases: window index 0, large window indices, and windows whose start timestamps fall near window boundary edges.

Do not change the on-disk log file format (the binary layout described in README.md must remain byte-for-byte identical). Do not change the config schema: the top-level keys and value types in /app/audit-stack/config.json must remain unchanged.

The stack can be exercised with:
  node /app/audit-stack/run.js --verify

The verifier exit code and per-window status are the ground truth for whether a window decrypts correctly.
