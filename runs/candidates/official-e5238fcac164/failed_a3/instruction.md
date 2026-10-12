Hey, our NetFlow settlement aggregator at /app is producing wrong per-counterparty byte totals for some traffic classes — the numbers don't match what the routers report via SNMP. Nobody left a repro.

The rules are: (1) each data flowset record's byte count must be attributed to the counterparty identified by the source-IP-to-ASN mapping table at /app/data/asn_map.csv, (2) when a flow template is re-exported mid-file the aggregator must use the most-recently-seen field layout for all subsequent records in that file, and (3) multi-file runs must carry template state forward across files in the order the files are processed (sorted by filename).

Fix /app so that running `python /app/settle.py /app/data/` produces a `settlement.csv` whose per-counterparty totals match the reference computation for any valid set of NetFlow v9 binary input files.
