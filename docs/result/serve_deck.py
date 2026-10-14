"""Serve docs/result/ over HTTP on an automatically chosen free port so `make deck` never conflicts."""
import http.server
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parent

Handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
with http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
    print(f"Deck opened at http://127.0.0.1:{server.server_port}/presentation.html (Ctrl-C to stop)")
    server.serve_forever()
