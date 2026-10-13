# Telemetry Attribution & Metric Query Service

This directory contains the codebase for `telemetry-queryd`, the local HTTP query and attribution daemon.

## Quick Links
- Full specification & schemas: `docs/spec.md`
- Legacy binary format C headers: `legacy/bpack.h`
- Legacy unpacker prototype: `legacy/sample_unpack.c`
- Logs directory: `/var/log/telemetry/` (`frontend/` and `backend/`)

## Service Management
- Port: `8085` (`0.0.0.0:8085`)
- Run script: `/opt/telemetry-service/run.sh {start|stop|restart|status}`
- Systemd service: `telemetry-queryd.service` (`systemctl restart telemetry-queryd`)
