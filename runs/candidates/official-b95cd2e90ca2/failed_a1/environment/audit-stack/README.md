# Encrypted Audit Log Stack

This stack captures DB query latency metrics and stores them in encrypted, rotation-windowed audit logs.
Each log rotation window uses an ephemeral ECDH keypair to derive a unique AES-256-GCM session key.

## Architecture

The stack has three main services:

1. **metrics_collector.js** - Samples DB query latency at configurable intervals and pushes records to the encryptor.
2. **session_key_manager.js** - Generates ephemeral ECDH P-256 keypairs per rotation window, derives a shared secret with the server long-lived public key, and runs HKDF to produce a 32-byte AES session key.
3. **encryptor.js** - Calls the session key manager, encrypts batches of metric records using AES-256-GCM, and writes them with a structured binary header.
4. **log_rotator.js** - Manages rotation window indices and triggers log rotation every N records.
5. **verifier.js** - Reads encrypted log files, re-derives session keys using the server private key and the ephemeral public key stored in each log header, and decrypts to verify integrity.
6. **run.js** - CLI entry point.

## Session Key Derivation

For each rotation window, the session key is derived as follows:

```
initial_epoch = floor(window_start_ms / window_duration_ms) * window_duration_ms
ecdh_shared_secret = ECDH(ephemeral_private_key, server_public_key)
session_key = HKDF(
  ikm    = ecdh_shared_secret,
  salt   = floor(window_start_ms / window_duration_ms) * window_duration_ms  (as 8-byte big-endian UInt64),
  info   = window_index encoded as big-endian 8-byte unsigned integer,
  length = 32
)
```

The HKDF hash algorithm is SHA-256. The salt is the window start epoch in milliseconds, truncated to the nearest window boundary using integer division (floor). The info field is the window index encoded as a big-endian 8-byte (64-bit) unsigned integer.

## On-Disk Log Format

Each log file is a binary file with the following layout:

```
[4 bytes]  Magic: 0x41554C47 ("AULG")
[2 bytes]  Format version: 0x0001
[8 bytes]  Window index (big-endian uint64)
[4 bytes]  Ephemeral public key length (big-endian uint32)
[N bytes]  Ephemeral public key (DER/uncompressed)
[4 bytes]  Number of records (big-endian uint32)
--- for each record ---
[4 bytes]  Record length (big-endian uint32)
[12 bytes] AES-GCM IV/nonce
[16 bytes] AES-GCM auth tag
[M bytes]  Ciphertext
```

## Configuration Schema

All services share `/app/audit-stack/config.json`:

```json
{
  "server": { "privateKey": "<base64 PKCS8>", "publicKey": "<base64 SPKI>" },
  "rotation": { "windowDurationMs": 15000, "recordsPerWindow": 15 },
  "hkdf": { "hashAlgorithm": "sha256", "keyLength": 32 },
  "logging": { "logDir": "/app/audit-stack/logs", "stateFile": "/app/audit-stack/state.json" },
  "metrics": { "sampleIntervalMs": 500, "dbQueryLatencyBaseMs": 12 }
}
```

## State Tracking

`state.json` tracks the current rotation window:

```json
{
  "lastWindowIndex": 14,
  "lastWindowStartMs": 1700000000000
}
```

## Dashboard

`dashboard.json` reports per-window verification status after a run.
