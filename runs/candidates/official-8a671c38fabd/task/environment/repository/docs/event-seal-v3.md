# Event Seal protocol v3

Events are encoded as compact UTF-8 JSON. Objects are recursively emitted with keys sorted by Unicode code point; arrays retain order. Strings use JSON escaping. Numbers are finite JSON numbers emitted by the ECMAScript JSON number algorithm. Null, booleans, empty objects, and empty arrays are retained.

A rotation is `{ "id": string, "effectiveAt": integer, "key": base64url }`. For each event choose the rotation with greatest effectiveAt less than or equal to event.timestamp; ties use the first input record. Decode key as unpadded base64url bytes. Let K be HKDF-SHA256 with IKM equal to those bytes, empty salt, info UTF-8 `event-seal-v3/` followed by the id, and length 32.

Set C0 to SHA256 of UTF-8 `event-seal-v3-chain`. For event index i, N is the first 12 bytes of HMAC-SHA256(K, C || uint64be(i) || canonicalEventBytes). Encrypt canonicalEventBytes using AES-256-GCM with K and N, with C as additional authenticated data. Set Cnext to SHA256(C || N || ciphertext || tag). Each entry is `{index,keyId,nonce,ciphertext,tag}` with byte fields encoded as unpadded base64url. The manifest is `{version:3,entries,root,signatures:[]}`, where root is the final C encoded as unpadded base64url, or C0 for an empty batch.
