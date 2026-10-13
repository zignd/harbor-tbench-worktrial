# Telemetry session attribution service

This service reconstructs end-to-end requests from legacy frontend access logs and backend worker execution packs. The ingress proxy no longer propagates trace identifiers, so frontend and backend records are joined only by the temporal and semantic constraints in `docs/spec.md`.

## Layout

- `daemon.py` is the HTTP entry point.
- `docs/spec.md` is the authoritative protocol and attribution specification.
- `legacy/bpack.h` describes the compact backend log format.
- `tools/generate_baseline.py` creates local sample packs for development.
- `run.sh` manages the daemon with `start`, `stop`, `restart`, `status`, and `foreground`.

The daemon reads `/var/log/telemetry/frontend/*.tsv` and `/var/log/telemetry/backend/*.bpack` on demand and uses port 8085 by default. `TELEMETRY_PORT` may override the port in development. Logs are written to `/var/log/telemetry-service.log` when the daemon is managed by `run.sh`.
