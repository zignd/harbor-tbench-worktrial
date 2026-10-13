Incident recovery notes

The field is the decimal prime p = 2305843009213693951. Shares are points (x,y) on a degree threshold-1 polynomial over this field. The epoch secret is f(0), and commitment is SHA-256 of its unsigned big-endian 8-byte representation. Recoveries must try combinations rather than trusting row order.

The event MAC is HMAC-SHA256 with the recovered secret represented as the unsigned big-endian 8-byte key. The message is the UTF-8 concatenation of epoch, a colon, sequence, a colon, predecessor digest, a colon, account, a colon, and payload. Digest values are lowercase hexadecimal SHA-256 hashes of the same canonical event text. A checkpoint signature is HMAC-SHA256 over epoch:sequence:digest using the epoch key.

Only a path beginning at the recorded anchor, with sequence zero followed by each contiguous sequence, and ending at a valid terminal checkpoint is authoritative. Events may be individually authentic without being part of such a path.
