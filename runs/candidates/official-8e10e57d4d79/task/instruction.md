Make `/opt/relay/deploy.sh` executable and use it to deploy the complete sensor wire relay in this container. The TCP ingest service must listen on port 9100, and the event service must listen on HTTP port 9200 with working `/health` and `/metrics` endpoints.

The deployment must be restart-safe: running the deployment command repeatedly must leave exactly one healthy ingest path and one healthy event service, with stale processes, sockets, and pid files cleaned up. All services must be ready before the deployment command returns.

Every valid generated wire event must produce exactly one corresponding JSON event at the event service. Preserve its identifier, sequence number, timestamp, measurements, and metadata, and preserve input ordering within a connection. Frames may be fragmented across arbitrary TCP writes or concatenated in one write. Malformed magic, lengths, versions, checksums, and frame contents must be rejected without closing the long-lived ingest connection or affecting valid frames that follow them. Unknown optional metadata fields must be tolerated.

The deployed relay must remain reliable across input and event-service reconnects, must not duplicate acknowledged identifiers, and must not lose acknowledged events. It must process at least 99.5% of valid events and sustain at least 1,800 correctly processed events per second on the verifier workload.
