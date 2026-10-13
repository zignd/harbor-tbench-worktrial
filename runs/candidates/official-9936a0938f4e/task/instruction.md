The fingerprint extractor at /app/extractor/extract.py must produce output identical to /app/bin/ref_fingerprint for every ClientHello the replay service emits on port 7823. Run the extractor as:

    python /app/extractor/extract.py <host> <port>

It connects to the given host:port, reads TLS records sent by the replay service, and prints one fingerprint string per ClientHello to stdout, one per line, in arrival order.

The fingerprint format is:

    SSLVersion,Ciphers,Extensions,EllipticCurves,EllipticCurvePointFormats

where each field is a dash-separated list of decimal integers. GREASE values (RFC 8701 two-byte reserved codes matching the pattern 0x?A?A where both bytes are equal) must be stripped from every field before formatting. If a field has no values after filtering, it is empty. The five fields are always present, separated by commas.

The extractor must correctly handle ClientHello records that are split across multiple TCP segments. It must handle ClientHellos with no extensions, with no SNI, with non-null compression methods, and with GREASE values in cipher suites, extension types, and elliptic curve group IDs.

The replay service is already running on port 7823. Each connection receives the full corpus in order; the stream ends when the server closes the connection.
