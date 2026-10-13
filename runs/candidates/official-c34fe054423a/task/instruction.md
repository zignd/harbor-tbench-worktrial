$ python /opt/ledgerforge/bin/report.py data/bad-day.rfx
ERROR: frame 7 has invalid payload length
reported total: 18446744073709551584

Implement the missing recovery feature in /opt/ledgerforge. Create an executable /opt/ledgerforge/bin/recover.py that accepts one archive path and an optional --out PATH argument. It must read the RFX archives used by this installation and write canonical UTF-8 JSON to the requested output path, or to stdout when --out is omitted.

The JSON must contain records, total, and status. records must contain every recoverable logical observation exactly once, ordered by sequence number. Each record must be an object with integer seq and value as a reduced fraction string. total must be the exact reduced rational sum, using 0 for zero, an integer string when the denominator is one, and p/q with a positive denominator otherwise. Do not use binary floating point.

status must be complete when all logical observations are present in valid data frames and recovered when damaged or truncated frame data was reconstructed using archive redundancy. Frames may be physically reordered, duplicated, damaged, or partially truncated. Valid zero and negative values, very large coefficients, negative decimal exponents, cancellation to zero, and encoded lengths crossing one-byte varint boundaries must work. Bad-checksum or malformed payloads must not contribute their unverified values.

Use the archive recovery information whenever a logical observation is recoverable. If any logical observation cannot be recovered, exit nonzero and emit a concise error rather than inventing a value. Results must be independent of physical frame order, duplicate valid copies, and whether recovery was needed. Use only the Python standard library. Do not modify /opt/ledgerforge/bin/report.py or the supplied fixtures.
