# Telemetry Migration & Query Service

This directory contains the migration service skeleton for attributing edge requests to backend executions and computing latency quantiles.

## Components
- `docs/spec.md`: Complete API specification and attribution rules.
- `legacy/`: C headers (`bpack.h`) and sample unpacker for `.bpack` format.
- `app/`: Python service daemon code.
- `run.sh`: Service daemon control script (start, stop, restart, status).
- `telemetry-queryd`: Wrapper executable in PATH or service script.

## Service Ports
- HTTP port: `8085`
