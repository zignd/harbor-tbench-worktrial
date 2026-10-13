# Event Seal

This repository contains the cold-storage telemetry sealing pipeline. The command-line entry points read JSON event arrays and rotation schedules and emit compact manifests. Supporting tools provide validation, partition metrics, and rotation schedule checks.

The protocol contract is in `docs/event-seal-v3.md`. Library consumers should import `sealBatch` from `src/index.js`; callers must pass the complete event list and rotation schedule rather than implementing authentication locally.
