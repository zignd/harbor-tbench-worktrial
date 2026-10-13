# Encrypted Log Format

Each microservice's logs are encrypted with a per-service symmetric key before
transmission. The same key is used for all log files from a given service.

## Key Derivation

The per-service key is derived from the master key using HKDF (HMAC-based Key
Derivation Function) as follows:

- Algorithm: HKDF with SHA-256
- Salt: empty (not used)
- Info: the service name as a UTF-8 string (e.g. "auth", "payments", "gateway")
- Output length: 32 bytes (256 bits)

In Python pseudo-code:

    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives import hashes

    derived_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=service_name.encode('utf-8'),
    ).derive(master_key.encode('utf-8'))

## Encryption

Each log file is encrypted using ChaCha20, a 256-bit stream cipher. Every file
has its own random nonce.

### File Format

Each .enc file consists of three parts concatenated without separators:

1. Nonce length (4 bytes): a little-endian unsigned 32-bit integer specifying
the length of the nonce in bytes. For ChaCha20 this is always 16.

2. Nonce (N bytes): the random nonce used to encrypt this file.

3. Ciphertext (remaining bytes): the ChaCha20-encrypted plaintext, using the
256-bit derived key and the nonce from step 2.

### Decryption Process

1. Read the first 4 bytes to obtain the nonce length (little-endian uint32).
2. Read the next N bytes as the nonce.
3. Read the remainder of the file as the ciphertext.
4. Decrypt using ChaCha20 with:
   - Key: the 32-byte derived key (see above)
   - Nonce: the N bytes read in step 2

The plaintext is valid UTF-8 text.

## Log Line Format

Each decrypted line has the format:

    YYYY-MM-DDTHH:MM:SS.mmmmmm Z [SEQ_NUM] message text

Where:
- Timestamp: ISO 8601 with microsecond precision and trailing Z (UTC).
- Sequence number: a unique integer per service, enclosed in brackets, starting
  from 1 and incrementing by 1 for each record.
- Message: free-form text (cannot contain newlines).

## Pipeline

The pipeline (`/app/pipeline.py`) processes all .enc files under
`/app/logs/<service>/` for each service listed in `/app/config.yaml`,
decrypts them, extracts and sorts records, deduplicates by (service, sequence
number), and writes the combined output to `/app/output/combined.log`.

It maintains a state file at `/app/state/processed.json` to avoid
reprocessing sequence numbers that were already written on previous runs.
This file maps service names to sets of sequence numbers that have been
processed.
