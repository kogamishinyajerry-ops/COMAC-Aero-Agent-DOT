"""Local-only stdlib HTTP app. No keys, uploads, installs or external calls."""
from __future__ import annotations
import argparse
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.parse import urlparse
from .model import catalog, compare, simulate, sweep
from .evidence import read_reference

ROOT = Path(__file__).resolve().parent.parent
COMPUTE_LOCK = threading.Lock()
MAX_BODY = 4096
ALLOWED_ARGS = {"scenario_id", "policy", "design_id", "ambient_c", "dt_s", "demand_scale", "event_time_offset_s"}


@lru_cache(maxsize=1)
def replay_bytes():
    result = read_reference()
    for run in result.values():
        run["meta"]["execution"] = "replay"
    return json.dumps(result, ensure_ascii=False, allow_nan=False).encode()


class Handler(BaseHTTPRequestHandler):
    server_version = "AeroLab/0.1"

    def send_bytes(self, code, data, mime="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, code, result):
        self.send_bytes(code, json.dumps(result, ensure_ascii=False, allow_nan=False).encode())

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/catalog":
            return self.send_json(200, catalog())
        if path == "/api/replay":
            try:
                return self.send_bytes(200, replay_bytes())
            except (OSError, ValueError) as exc:
                return self.send_json(503, {"error": str(exc)})
        routes = {"/": ("index.html", "text/html; charset=utf-8"),
                  "/index.html": ("index.html", "text/html; charset=utf-8"),
                  "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                  "/styles.css": ("styles.css", "text/css; charset=utf-8")}
        if path not in routes:
            return self.send_json(404, {"error": "Not found"})
        filename, mime = routes[path]
        target = ROOT / "web" / filename
        if not target.is_file():
            return self.send_json(503, {"error": "UI not available"})
        return self.send_bytes(200, target.read_bytes(), mime)

    def do_POST(self):
        # Same-origin local requests only; never enable broad browser CORS.
        origin = self.headers.get("Origin")
        host = self.headers.get("Host")
        if origin and origin not in (f"http://{host}", f"https://{host}"):
            return self.send_json(403, {"error": "Cross-origin requests are disabled"})
        path = urlparse(self.path).path
        if path not in ("/api/run", "/api/compare", "/api/sweep"):
            return self.send_json(404, {"error": "Unknown operation"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_BODY:
                raise ValueError("Request body must contain 1–4096 bytes")
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict) or set(body) - ALLOWED_ARGS:
                raise ValueError("Invalid or unknown request fields")
            if not COMPUTE_LOCK.acquire(blocking=False):
                return self.send_json(429, {"error": "A calculation is in progress; try again when it completes"})
            try:
                function = {"/api/run": simulate, "/api/compare": compare, "/api/sweep": sweep}[path]
                result = function(**body)
            finally:
                COMPUTE_LOCK.release()
            return self.send_json(200, result)
        except (ValueError, TypeError) as exc:
            return self.send_json(400, {"error": str(exc)})


def serve(host="127.0.0.1", port=8765):
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("This development server only binds to loopback")
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Synthetic mission lab: http://{host}:{httpd.server_port}", flush=True)
    print("Local development only. Not an operational aircraft-control service.", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
