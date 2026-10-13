Beacon Catalog Protocol

The service listens on TCP port 4711. Each connection accepts multiple UTF-8 JSON objects, one per newline, and returns one JSON object per request. Objects are compact but field names are fixed.

A successful lookup is {"ok":true,"generation":N,"device":"16 uppercase hex characters","value":integer,"quality":integer,"source_sequence":integer}. The timestamp `at` is inclusive: the selected observation is the latest observation at or before it. If the device is absent or no observation is at or before `at`, return {"ok":false,"error":"not_found"}. Invalid fields or JSON return {"ok":false,"error":"invalid_request"}; an unknown operation returns {"ok":false,"error":"unknown_operation"}.

A successful history is {"ok":true,"generation":N,"device":"...","records":[{"at":integer,"value":integer,"quality":integer,"source_sequence":integer},...]}. Both from and to are inclusive. Records are ordered by the device's canonical source order: unsigned 32-bit sequence distance from the first retained sequence, then timestamp, then source_sequence, and duplicate observations (same device, timestamp) retain the highest quality, then the later canonical sequence. An absent device has an empty records array. If from is greater than to return invalid_request.

Stats is {"ok":true,"generation":N,"devices":integer,"records":integer,"rejected_frames":integer}. Reload is {"ok":true,"generation":N,"devices":integer,"records":integer,"rejected_frames":integer}; it rebuilds from /opt/beacon/data. Generation increases for every successful reload and all fields in one response come from one generation.
