metricq reads JSON objects, one per line, from stdin and emits one JSON object per line. State is in /opt/metricq/state and diagnostics are in /opt/metricq/logs/service.log.

{"op":"reset","lateness":10} returns {"ok":true}. lateness is an optional nonnegative timestamp-unit tolerance and defaults to 10.
{"op":"ingest","stream":"s","event_id":"e","timestamp":12,"value":3.5,"weight":2} returns {"ok":true,"accepted":true,"duplicate":false}; weight is positive and defaults to 1.
{"op":"query","stream":"s","start":0,"end":20,"quantile":0.5} returns {"ok":true,"stream":"s","start":0,"end":20,"quantile":0.5,"value":3.5,"weight":2,"count":1}, or value:null, weight:0, count:0 for an empty range. The interval is [start,end).
{"op":"checkpoint"} returns {"ok":true,"offset":N}. It persists state and the next journal byte offset.
{"op":"recover"} returns {"ok":true,"recovered":N,"offset":N}. It is safe to repeat.
Invalid complete requests return {"ok":false,"error":"invalid_request"}; unknown operations return {"ok":false,"error":"unknown_operation"}.
