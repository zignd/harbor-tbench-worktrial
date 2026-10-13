# Event Seal Protocol v3
Canonical bytes are compact UTF-8 JSON. Sort object keys recursively, preserve array order, use JSON literals and ECMAScript finite-number syntax, and reject non-finite numbers.
For event i choose the last rotation with from <= i. Decode its unpadded base64url key, then derive HKDF-SHA256(raw, salt UTF8 event-seal-v3, info UTF8 id, length 32). AES-256-GCM uses the canonical bytes, empty AAD, and nonce uint32be(i) followed by eight zero bytes. Auth is ciphertext plus the 16-byte tag.
Starting from 32 zero bytes, chain SHA256(previous || UTF8(id) || uint32be(i) || auth). The manifest is version, entries of index/key/auth/chain, root, and empty signatures; byte fields use unpadded base64url.
