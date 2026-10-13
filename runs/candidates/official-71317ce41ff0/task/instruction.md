The `librecenc` library encrypts individual SQLite table rows with AES-128-CTR, deriving a per-record nonce from the record's primary key and a domain separator. The library was recently refactored from a working proof-of-concept into a modular production system split across six source files. The refactor passes the 12 provided regression tests but produces wrong plaintexts for records outside the test corpus. Decryption reports no error but the decrypted values are incorrect.

The library source is in `/app/librecenc/`. The reference binary from before the refactor is at `/app/artifacts/librecenc_ref.so` (a shared library exposing the same API). The master key is at `/data/master.key` and the encrypted dataset is at `/data/experiment.db`.

Fix the library so that:
1. Encrypting any record with the library and decrypting it with the same library returns the original plaintext exactly.
2. Encrypting a record with the library and decrypting it with `/app/artifacts/librecenc_ref.so`, or vice versa, returns the original plaintext exactly. The wire format and nonce construction must be identical to the reference.
3. Records with empty string fields, fields whose serialized length is a multiple of 16 bytes, records with `record_id` values that are powers of two up to 2^32, and multi-field records where the total serialized length crosses a 256-byte boundary all round-trip correctly.
4. Build the fixed library as `/app/librecenc/librecenc.so` and the CLI tool as `/app/bin/recenc`.

Running `/app/repro_check --db /data/experiment.db --key-file /data/master.key` must print `Reproduction check: PASS`.
