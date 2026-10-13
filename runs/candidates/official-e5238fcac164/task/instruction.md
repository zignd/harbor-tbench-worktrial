Our NetFlow settlement aggregator at /app is producing wrong per-counterparty byte totals for some traffic classes — the numbers don't match what the routers report via SNMP. No reproduction script was left.

The service reads NetFlow v9 binary files from a directory, looks up each flow's source IP in /app/data/asn_map.csv (a CIDR-prefix-to-ASN mapping table), and writes per-counterparty byte totals to settlement.csv in the current working directory.

The rules are: each data flowset record's byte count must be attributed to the counterparty identified by the source-IP-to-ASN mapping table; when a flow template is re-exported mid-file the aggregator must use the most-recently-seen field layout for all subsequent records in that file; multi-file runs must carry template state forward across files in the order the files are processed, sorted by filename.

Fix /app so that running `python /app/settle.py /app/data/` produces a settlement.csv whose per-counterparty byte totals match the reference computation for any valid set of NetFlow v9 binary input files.
