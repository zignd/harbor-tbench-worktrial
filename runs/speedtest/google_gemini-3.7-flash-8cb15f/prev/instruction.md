Complete the telemetry session attribution and query daemon in /opt/telemetry-service so it serves log attribution and aggregation metrics on port 8085.

Frontend access logs are in /var/log/telemetry/frontend/ (*.tsv) and backend execution logs are in /var/log/telemetry/backend/ (*.bpack). Detailed log schemas, binary record layout (also defined in /opt/telemetry-service/legacy/bpack.h), session attribution constraints, percentile definitions, and REST schemas are specified in /opt/telemetry-service/docs/spec.md.

The HTTP daemon must listen on 0.0.0.0:8085 and implement GET /healthz, GET /v1/attribution/stats, and POST /v1/query according to /opt/telemetry-service/docs/spec.md. It must dynamically incorporate any new log files added to /var/log/telemetry/frontend/ and /var/log/telemetry/backend/.

Ensure the daemon runs in the background and that systemctl restart telemetry-queryd (or /opt/telemetry-service/run.sh) leaves the service running and healthy.
