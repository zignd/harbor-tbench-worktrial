# cython: language_level=3

import hmac as _hmac
import hashlib


def verify_chain_entry(entry_index, payload, stored_tag,
                        seed_hex, prev_tag_hex, current_tag_hex):
    if entry_index == 0:
        key = bytes.fromhex(seed_hex)
    else:
        key = _hmac.new(
            current_tag_hex.encode("ascii"),
            b"key",
            hashlib.sha256
        ).digest()

    computed_tag = _hmac.new(
        key,
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return computed_tag == stored_tag
