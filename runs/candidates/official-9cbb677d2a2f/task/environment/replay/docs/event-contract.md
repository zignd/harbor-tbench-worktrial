# Event contract

Timestamps are normalized ISO-8601 UTC text. Alias intervals are half-open: valid_from is included and valid_to is excluded. Correlation uses the resolved actor identity and incident_key; a nonempty merge_key connects all events carrying that key, transitively.

Dependencies refer to event ids. Edges are applied only when both endpoints are in the component. Available vertices are selected by `(timestamp, source sequence, event id)`. A cyclic remainder emits its smallest such key and then continues. This makes ordering independent of insertion order.

Archival data is immutable. A tombstone removes its own logical event. `supersedes` removes the referenced logical event after all source rows have been archived. Canonical transitions are open, ack, and resolve events surviving that reduction. The policy interval containing each transition timestamp supplies its version and response window.
