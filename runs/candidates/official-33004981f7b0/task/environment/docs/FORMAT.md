Settlement spool format v1

A spool is a sequence of frames. Each frame begins with the ASCII magic `STL1`, one version byte, one kind byte, a big-endian uint16 header length, and a big-endian uint32 payload length. The header is JSON encoded and the payload is authenticated binary data. The final 32 bytes of each frame are its SHA-256 authentication tag over the preceding frame bytes and the manifest context. A transaction payload is JSON; an adjustment has kind `adjustment`, a signed integer `amount`, and a `reference` string. Every transaction reference, not merely its display id, identifies a record.

The bank CSV columns are `reference,amount,currency`. Amounts are integer minor units and are post-adjustment final amounts. Adjustments are applied to transaction records before reconciliation. Canonical audit leaves are SHA-256 of the UTF-8 JSON object with sorted keys and compact separators; the chain starts at 32 zero bytes and hashes the prior root concatenated with each leaf in reference-byte order. Reports use integer fields and stable sorted JSON keys.

Diagnostic: bank CSV amounts are post-adjustment final amounts; adjustments must be applied to transaction records before reconciliation; a complete valid batch reports status "balanced" when those final amounts reconcile.
