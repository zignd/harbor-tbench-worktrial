import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8085

class TelemetryRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/healthz":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "healthy"}).encode("utf-8"))
            return
        elif self.path == "/v1/attribution/stats":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {
                "total_frontend_records": 0,
                "total_backend_records": 0,
                "matched_records": 0,
                "unmatched_frontend": 0,
                "unmatched_backend": 0,
                "mean_slack_ms": 0.0
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/v1/query":
            content_len = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_len)
            self.send_response(501)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not implemented"}).encode("utf-8"))
            return
        else:
            self.send_response(404)
            self.end_headers()

def main():
    server_address = ("0.0.0.0", PORT)
    httpd = HTTPServer(server_address, TelemetryRequestHandler)
    print(f"telemetry-queryd listening on 0.0.0.0:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()

if __name__ == "__main__":
    main()
