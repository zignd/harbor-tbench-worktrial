[ERROR] Service 'payment-processor' failed to initialize. Critical error detected. Attempting to retrieve historical logs for diagnostics.
[INFO] Log decryption failed. Encrypted log file found at /var/log/payment-processor.log.enc
[WARN] Fallback log acquisition failed. Manual intervention required.

Your mission is to decrypt the provided log file and reconstruct the original log content. The decryption mechanism is a custom XOR-based cipher with a key derived from a known system parameter. Analyze the provided system files to identify the encryption key and algorithm, then decrypt and output the original log content to stdout. The system contains an in-house Python logging utility and configuration files that might offer clues.
