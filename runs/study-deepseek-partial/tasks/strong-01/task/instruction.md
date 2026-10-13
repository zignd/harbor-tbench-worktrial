The packet filter at /app/filter.sh takes a single base64-encoded packet as its argument and must output either ACCEPT or REJECT on stdout, then exit. It uses /app/config/allowlist.txt to decide which device IDs are permitted and /app/bin/check_crc16 to verify the checksum of each packet.

A git repository at /app stores the history of this filter. The initial commit contains the script, the allowlist, the binary, and a few sample packets under /app/samples/ that are currently handled correctly. A second commit added /app/config/blocklist.txt listing revoked device IDs.

Lately the filter has been misbehaving: some packets that should be accepted are being rejected, and some that should be rejected are getting through. Fix the script so that every valid packet is accepted and every invalid packet is rejected, using the information already available under /app.
