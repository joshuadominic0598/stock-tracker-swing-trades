"""HTTP transport, loopback protection and static file delivery."""

import json
import mimetypes
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse

from swing_signal.http import routes
from swing_signal.paths import WEB_ROOT

class Handler(BaseHTTPRequestHandler):
    def local_host(self):
        """Keep loopback services inaccessible through an attacker-controlled hostname."""
        hosts = self.headers.get_all("Host", [])
        if len(hosts) != 1:
            return False
        port = self.server.server_port
        return hosts[0].lower() in (f"127.0.0.1:{port}", f"localhost:{port}")

    def log_message(self, fmt, *args):
        if self.path.startswith("/api/") and "?" in self.path:
            return
        if "/api/overview" not in str(args):
            super().log_message(fmt, *args)

    def reply(self, value, status=200):
        raw = json.dumps(value, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if not self.local_host():
            return self.reply(dict(error="Use this app through its localhost address"), 403)
        try:
            parsed = urlparse(self.path)
            response = routes.get(parsed.path, parsed.query)
            if response is not None:
                return self.reply(*response)
            relative = "index.html" if parsed.path == "/" else parsed.path.lstrip("/")
            target = (WEB_ROOT / relative).resolve()
            if not target.is_relative_to(WEB_ROOT) or not target.is_file():
                return self.reply(dict(error="File not found"), 404)
            raw = target.read_bytes()
            self.send_response(200)
            self.send_header(
                "Content-Type", mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            )
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except ValueError as exc:
            self.reply(dict(error=str(exc)), 400)
        except Exception as exc:
            self.reply(dict(error=str(exc)), 500)

    def do_POST(self):
        if not self.local_host():
            return self.reply(dict(error="Use this app through its localhost address"), 403)
        try:
            origin = self.headers.get("Origin")
            if origin and origin != "http://" + self.headers.get("Host", ""):
                return self.reply(dict(error="Cross-origin changes are disabled"), 403)
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                raise ValueError("Use application/json")
            size = int(self.headers.get("Content-Length", "0"))
            if size < 0:
                raise ValueError("Content-Length must be non-negative")
            if size > 4_000_000:
                return self.reply(dict(error="Request is too large"), 413)
            body = json.loads(self.rfile.read(size) or b"{}")
            if not isinstance(body, dict):
                raise ValueError("Use a JSON object")
            return self.reply(*routes.post(urlparse(self.path).path, body))
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            self.reply(dict(error=str(exc)), 400)
        except Exception as exc:
            self.reply(dict(error=str(exc)), 500)
