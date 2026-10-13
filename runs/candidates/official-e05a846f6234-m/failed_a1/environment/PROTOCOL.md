metricq JSON-lines protocol

Every request is one JSON object. Every response is one compact JSON object. Invalid requests return exactly `{"ok":false,"error":{"code":"invalid_request","message":string}}`.

reset is `{"op":"reset"}` and returns `{"ok":true,"reset":true}`. It clears the journal and all state.
ingest is `{"op":"ingest","stream":string,"id":string,"ts":number,"value":number,"weight":positive integer}` and returns `{"ok":true,"accepted":boolean}`. Duplicate identities return accepted false without adding a record. A distinct event is accepted when its timestamp is no older than 10 units below that stream's maximum timestamp; equality at the cutoff is accepted. Identity is checked before lateness.
query is `{"op":"query","stream":string,"start":number,"end":number,"q":number}` or the same with a nonempty array for q. It returns `{"ok":true,"values":number|null}` for scalar q, or an array for q array. The range is half-open `[start,end)`. Empty ranges return null or null entries.
checkpoint is `{"op":"checkpoint"}` and returns `{"ok":true,"offset":integer}`. The offset is the first uncommitted journal record.
recover is `{"op":"recover"}` and returns `{"ok":true,"recovered":integer,"offset":integer}`. It restores the checkpoint and replays records after its offset. An incomplete final line is dropped safely. A complete malformed line returns the standard invalid-request error.

Weights are positive integers. Values and times must be finite numbers. Query end must exceed start and quantiles must be finite numbers in [0,1]. Weighted percentile sorts observations by value and selects the first value whose cumulative weight exceeds q*(total_weight-1); q=0 selects the minimum. JSON field order is stable.
