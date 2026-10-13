ALERT [03:14 UTC]: canary=payments-v2 PROMOTED_TO_100PCT | p99_error_rate=23.4% | 847 downstream 5xx in 5min | PagerDuty #INC-4821

The canary orchestrator at /app promoted a broken deployment without rolling back. The orchestrator feeds incoming request telemetry through /app/bin/traffic-sampler (pre-compiled, no source) before updating its health window and deciding whether to promote or roll back.

Fix the orchestrator so that all of the following hold when the service is restarted with node /app/src/server.js:

1. A canary whose sampled error rate exceeds config.errorThreshold (default 0.10) for at least config.minSamples (default 50) samples enters 'rolledback' phase and never advances to 'promoted'.

2. Health-window state and accumulated sample counts survive a configuration reload triggered by POST /api/reload or the periodic 30-second watcher.

3. GET /api/status returns JSON with at minimum: { phase, sampleCount, sampledErrorRate, stableVersion, canaryVersion }.

4. POST /api/rollback immediately sets phase to 'rolledback' regardless of current health.

5. The rollback-decider module at /app/src/rollback-decider.js must be fully implemented and make correct promote/rollback decisions based on the health window state.

6. POST /api/telemetry accepts { statusCode, latencyMs, weight } records, routes them through the sampler pipeline, and updates the health window. The error rate calculation must correctly reflect the original request outcome, using the weight field from each record for weighted averaging.

The /app/docs/sampler-protocol.md describes the binary's input/output format and weight field semantics. The configuration is at /app/config/default.json. Historical logs are in /app/logs/.
