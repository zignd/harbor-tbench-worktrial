# metricq protocol
Each input line is one JSON request and each request produces one compact JSON response.
reset clears state. ingest requires stream, id, ts, value and optional positive integer weight. query requires stream, start, end and q, where q is a number or array of numbers from 0 through 1. checkpoint persists state and returns an offset. recover restores the checkpoint and replays committed journal records.
Successful ingest returns ok and accepted; duplicate identities return accepted false. Query windows are [start,end). Invalid complete requests return {"ok":false,"error":{"code":"invalid_request","message":"..."}}.
