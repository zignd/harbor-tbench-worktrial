The audit service at `/app/bin/logaudit` must accept TCP connections on port 7741. For each newline-terminated hex-encoded WAL record it receives, it must respond with a newline-terminated lowercase hex HMAC-SHA256 tag computed over the canonical binary form of the record using the key in `/app/etc/audit.key`.

The binary record format is documented in `/app/src/wal_record.c`. Refund-type records carry a `charge_txid` field identifying the charge transaction they reverse. If that field is zero when the record arrives, the service must look up the correct `charge_txid` in `/app/var/audit.db` and populate the field before computing the tag. The database schema and the resolver logic are in `/app/sql/` and `/app/src/refund_resolver.c`.

Records of every type and length must be handled correctly. The binary payload may be up to 65535 bytes, making the hex-encoded form up to 131070 characters per line. A malformed hex string (odd length or invalid characters) must produce `ERR` on that line without terminating the session; the next valid record in the same connection must still be answered correctly. State must remain consistent when multiple records arrive in the same TCP session.

The source is in `/app/src/`. Rebuild with `make` in `/app/` after any changes. The service can be started directly as `/app/bin/logaudit`.
