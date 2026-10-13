import http.server
import json
import os
import sys

PORT = 8085

class TelemetryHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    def _send_json(self, status_code, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/healthz":
            self._send_json(200, {"status": "healthy"})
        elif self.path == "/v1/attribution/stats":
            # TODO: Ingest logs, match trace sessions, and compute attribution stats
            self._send_json(501, {"error": "Not implemented: attribution engine not configured"})
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        if self.path == "/v1/query":
            # TODO: Implement windowed metric query aggregation
            self._send_json(501, {"error": "Not implemented: query engine not configured"})
        else:
            self._send_json(404, {"error": "Not found"})

def run():
    server_address = ("0.0.0.0", PORT)
    httpd = http.server.ThreadingHTTPServer(server_address, TelemetryHTTPRequestHandler)
    print(f"Starting telemetry-queryd on port {PORT}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()

if __name__ == "__main__":
    run()
