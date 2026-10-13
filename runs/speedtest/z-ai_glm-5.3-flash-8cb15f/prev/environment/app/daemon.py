#!/usr/bin/env python3
"""HTTP entry point for telemetry-queryd."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from telemetry_service.attribution import AttributionResult
from telemetry_service.metrics import METRICS, query_metrics, summarize
from telemetry_service.store import TelemetryStore

STORE = TelemetryStore()


class QueryHandler(BaseHTTPRequestHandler):
    server_version = "telemetry-queryd/0.4"
    protocol_version = "HTTP/1.1"

    def _send_json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: int, message: str) -> None:
        self._send_json(status, {"error": message})

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/healthz":
            self._send_json(200, {"status": "healthy"})
            return
        if path == "/v1/attribution/stats":
            try:
                self._send_json(200, summarize(STORE.snapshot()))
            except Exception as exc:
                self._error(500, str(exc))
            return
        self._error(404, "not found")

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path != "/v1/query":
            self._error(404, "not found")
            return
        try:
            length_header = self.headers.get("Content-Length")
            if length_header is None:
                raise ValueError("missing Content-Length")
            length = int(length_header)
            if length < 0 or length > 1_048_576:
                raise ValueError("invalid request body size")
            body = self.rfile.read(length)
            request = json.loads(body)
            payload = validate_query(request)
            result = STORE.snapshot()
            response = query_metrics(
                result,
                payload["endpoint"],
                payload["time_range"][0],
                payload["time_range"][1],
                payload.get("metrics"),
            )
            self._send_json(
                200,
                {
                    "endpoint": payload["endpoint"],
                    "time_range": payload["time_range"],
                    "metrics": response,
                },
            )
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._error(400, str(exc))
        except Exception as exc:
            self._error(500, str(exc))

    def log_message(self, fmt: str, *args) -> None:
        return


def validate_query(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("request body must be an object")
    endpoint = value.get("endpoint")
    if not isinstance(endpoint, str) or not endpoint:
        raise ValueError("endpoint must be a nonempty string")
    time_range = value.get("time_range")
    if not isinstance(time_range, list) or len(time_range) != 2:
        raise ValueError("time_range must contain two integers")
    start_ms, end_ms = time_range
    if type(start_ms) is not int or type(end_ms) is not int or start_ms >= end_ms:
        raise ValueError("time_range must contain two increasing integers")
    metrics = value.get("metrics")
    if metrics is not None:
        if not isinstance(metrics, list) or any(
            not isinstance(item, str) or item not in METRICS for item in metrics
        ):
            raise ValueError("metrics contains an unsupported metric")
    return {"endpoint": endpoint, "time_range": [start_ms, end_ms], "metrics": metrics}


def main() -> None:
    port = int(os.environ.get("TELEMETRY_PORT", "8085"))
    server = ThreadingHTTPServer(("0.0.0.0", port), QueryHandler)
    server.daemon_threads = True
    print(f"telemetry-queryd listening on 0.0.0.0:{port}", flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
