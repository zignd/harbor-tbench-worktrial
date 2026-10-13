The logarithmic quantile sketch daemon log-metricd in /opt/log-metricd fails to start under systemd, violates theoretical relative error tolerances on heavy-tailed latency distributions, and fails query latency SLAs under concurrent ingestion load.

Fix the Go implementation in /opt/log-metricd and deploy the daemon so that:
1. The service is managed and running under systemd (systemctl is-active log-metricd returns active, and systemctl restart log-metricd functions cleanly), listening on 0.0.0.0:9090.
2. The HTTP API endpoints GET /healthz, POST /v1/streams/register, POST /v1/ingest, and POST /v1/query respond correctly.
3. For any quantile query q in (0, 1) on ingested value streams, estimated quantiles satisfy the theoretical relative error bound |v_est - v_exact| / v_exact <= alpha (where alpha is the configured maximum relative error).
4. Multi-stream bucket allocations via POST /v1/streams/register satisfy the global bucket capacity constraint sum(B_i) <= B_total without dropping valid values in configured dynamic ranges [x_min, x_max].
5. Under concurrent load (ingestion bursts of at least 8,000 events/sec with concurrent query workers), the p99 response latency for /v1/query requests remains below 35ms.

You can run /opt/bench/run_sample.sh to run a sample benchmark verification.
