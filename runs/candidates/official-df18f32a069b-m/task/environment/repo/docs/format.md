# Contract document format

Documents are UTF-8 JSON objects. The required `name` string identifies the
contract. `parent`, when present, identifies another document by name. Fields
are an object whose values describe the wire type and optional nullability.
Policy is an object of named settings. Unknown policy settings remain part of
the resolved policy so that registry consumers can inspect them.

The registry is a JSON object with a contracts array. Each entry contains the
name, the complete resolved fields object, and effective policy. Diagnostics
are one JSON object per line and summaries contain accepted and rejected counts.
These files are intended for machines, so stable ordering and repeatable bytes
are part of the format contract.
