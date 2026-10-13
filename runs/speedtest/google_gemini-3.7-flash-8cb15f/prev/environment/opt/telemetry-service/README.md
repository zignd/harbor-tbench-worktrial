# Telemetry Session Attribution and Metric Query Service

This directory contains the telemetry query service (`telemetry-queryd`).

## Structure
- `docs/spec.md`: Detailed service and protocol specification.
- `legacy/bpack.h`: Legacy C header defining the `.bpack` binary log format.
- `legacy/sample_reader.c`: Legacy C sample reader utility.
- `telemetry_queryd.py`: Query daemon application.
- `run.sh`: Startup script for the service daemon.

## Service
The daemon runs on port `8085` and is managed via `/opt/telemetry-service/run.sh` or `systemctl restart telemetry-queryd`.
