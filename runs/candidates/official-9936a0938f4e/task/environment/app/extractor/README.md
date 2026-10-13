# TLS ClientHello Fingerprint Extractor

This tool connects to a packet replay service and produces fingerprint strings
from TLS ClientHello messages.

## Usage

    python extract.py <host> <port>

The extractor connects to the given host and port, reads a stream of TLS record
bytes, and prints one fingerprint per ClientHello to stdout.

## Fingerprint Format

The fingerprint follows the JA3 convention:

    SSLVersion,Ciphers,Extensions,EllipticCurves,EllipticCurvePointFormats

Each field is a dash-separated list of decimal integers. Fields may be empty
if the corresponding data is absent from the ClientHello.

GREASE filtering is applied before formatting: any GREASE extension values
are removed from all fields. GREASE values are defined in RFC 8701.

## Replay Protocol

The replay server prefixes each TLS record with a 4-byte little-endian length
field. The extractor reads the length, then reads that many bytes of TLS record
data. Multiple records are sent in sequence on the same connection.

## File Overview

- `extract.py` — main entry point; socket handling and fingerprint output
- `tls_types.py` — TLS constants (content types, handshake types, extension codes, etc.)
- `utils.py` — parsing helpers, GREASE detection, fingerprint formatting

## Notes on GREASE

GREASE values appear in cipher suites and extensions to test parser tolerance.
The is_grease() function in utils.py identifies these reserved values so they
can be excluded from fingerprints. The reference binary /app/bin/ref_fingerprint
applies the same filtering logic.
