# Audit Log HMAC Chain Specification

## Overview

Each log file produced by an application node consists of a header line followed
by zero or more entry lines. The chain ensures tamper-evidence: every entry's
HMAC-SHA256 tag is computed over the entry payload using a key derived from the
previous entry's tag.

## Log File Format

The log file is a plain text file. Lines are separated by real newline characters
(0x0A). Payloads that contain logical newlines encode them as the two-character
literal sequence `\n` (backslash followed by the letter n). Real newlines only
appear as line terminators.

### Header Line

```
AUDIT_LOG v1 node=<node_id> created=<ISO8601-timestamp>
```

The header line is metadata only. It is NOT counted as an entry; entry indices
start at 0 for the first data line after the header.

### Entry Line

Each entry is a single line with three fields separated by `|` (pipe):

```
<index>|<payload>|<hmac_tag>
```

- `index`: decimal integer, 0-based, counting only data entries (not the header)
- `payload`: arbitrary UTF-8 text; embedded newlines appear as literal `\n`
- `hmac_tag`: lowercase hex-encoded HMAC-SHA256 tag (64 hex characters)

## Key Derivation

Let `seed` be the 32-byte value obtained by hex-decoding the `seed` field from
`/app/config/chain.cfg`.

### Genesis Entry (index 0)

```
key_0 = seed
tag_0 = HMAC-SHA256(key=key_0, msg=payload_0)
```

### Subsequent Entries (index N > 0)

```
key_N = HMAC-SHA256(key=tag_{N-1}, msg=b'key')
tag_N = HMAC-SHA256(key=key_N, msg=payload_N)
```

Critical: `tag_{N-1}` in the key derivation step is the **raw bytes of the
hex-encoded tag string** of entry N-1 — that is, the ASCII/UTF-8 bytes of the
64-character lowercase hex string, NOT the 32 decoded binary bytes.

Example: if entry 0's tag is `"ab12..."` (64 hex chars), then
`key_1 = HMAC-SHA256(key=b'ab12...', msg=b'key')` where the key is the
64 ASCII bytes of that hex string.

## Verification Algorithm

1. Parse the log file. The first line is the header; skip it.
2. For each entry line (0-indexed), split on `|` to get index, payload, hmac_tag.
3. Compute the expected tag for each entry using the key derivation above.
4. Compare expected tag with stored hmac_tag (case-insensitive hex comparison).
5. If all match: the chain is valid.
6. If any mismatch: report the index of the first failing entry.

## Tamper Detection

- A tampered payload changes the HMAC input, so the stored tag will not match
  the recomputed tag.
- A tampered HMAC tag causes a direct mismatch and also corrupts the key for
  all subsequent entries.

## Protocol

The service reads lines from stdin and writes responses to stdout.

```
VERIFY <logfile>
```

Response: `OK <entry_count>` or `FAIL <first_bad_entry_index>`

```
QUERY <logfile> <entry_index>
```

Response: the exact payload string of that entry (a single line), or `NOTFOUND`
if the index is out of range or the file does not exist.

The service exits when stdin is closed.
