"""Single-owner, loopback-only Night Shift application."""
import argparse
import base64
import binascii
import hmac
import json
import os
import re
import secrets
import threading
import zipfile
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from engine import markdown
from demo_worker import DemoEngine as Engine
from provider import Mock, Ollama

HERE = Path(__file__).resolve().parent
STATIC = {"/": ("index.html", "text/html"), "/app.css": ("app.css", "text/css"),
          "/app.js": ("app.js", "text/javascript"),
          "/logo.png": ("logo.png", "image/png"),
          "/emblem.png": ("emblem.png", "image/png"),
          "/favicon.png": ("favicon.png", "image/png")}


class Server(ThreadingHTTPServer):
    allow_reuse_address = os.name != "nt"

    def __init__(self, engine, password, port):
        self.engine = engine
        self.credential = b"Basic " + base64.b64encode(("owner:" + password).encode())
        self.slots = threading.BoundedSemaphore(8)
        super().__init__(("127.0.0.1", port), Handler)

    def process_request(self, request, addr):
        if not self.slots.acquire(False):
            self.shutdown_request(request)
            return
        try:
            request.settimeout(8)
            super().process_request(request, addr)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, addr):
        try:
            super().process_request_thread(request, addr)
        finally:
            self.slots.release()


class Handler(BaseHTTPRequestHandler):
    server_version = "NightShift/1"

    def log_message(self, *args):
        pass

    def send(self, status, data, mime="application/json", filename=None):
        if not isinstance(data, bytes):
            data = json.dumps(data, ensure_ascii=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", mime + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if status == 401:
            self.send_header("WWW-Authenticate", 'Basic realm="Night Shift", charset="UTF-8"')
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(data)

    def handle_api(self):
        if not hmac.compare_digest(self.headers.get("Authorization", "").encode(), self.server.credential):
            return self.send(401, {"error": "Owner sign-in required"})
        path = self.path
        engine = self.server.engine
        if self.command == "POST":
            origin = self.headers.get("Origin")
            if (self.headers.get("X-Night-Shift") != "1" or
                    (origin and urlsplit(origin).netloc != self.headers.get("Host"))):
                return self.send(403, {"error": "Same-origin request required"})
        if self.command == "GET":
            if path in STATIC:
                name, mime = STATIC[path]
                return self.send(200, (HERE / "web" / name).read_bytes(), mime)
            if path == "/api/jobs":
                return self.send(200, {"mode": engine.provider.mode, "jobs": engine.list()})
        if path == "/api/jobs" and self.command == "POST":
            if self.headers.get_content_type() != "application/json" or self.headers.get("Transfer-Encoding"):
                return self.send(415, {"error": "Expected length-delimited JSON"})
            length = int(self.headers.get("Content-Length", "-1"))
            if not 1 <= length <= 6*1024*1024:
                return self.send(413, {"error": "Request exceeds upload limit or length missing"})
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError()
            if engine.provider.mode == "ollama" and data.get("cloud_consent") is not True:
                return self.send(400, {"error": "Confirm Ollama Cloud processing"})
            job = engine.submit(data.get("assignment"), data.get("files", []))
            return self.send(202, {"id": job})
        match = re.fullmatch(r"/api/jobs/([0-9a-f]{32})(?:/(cancel|report\.md|report\.json))?", path)
        if match:
            job, action = match.groups()
            if self.command == "POST" and action == "cancel":
                engine.cancel(job)
                return self.send(200, {"state": engine.get(job)["state"]})
            if self.command == "GET" and action != "cancel":
                record = engine.get(job)
                if not action:
                    return self.send(200, record)
                report = record["report"]
                if not report:
                    return self.send(409, {"error": "Report unavailable"})
                md = action.endswith(".md")
                return self.send(200, markdown(report).encode() if md else report,
                                 "text/markdown" if md else "application/json", f"night-shift-{job[:8]}-{action}")
        self.send(404, {"error": "Unknown route"})

    def do_GET(self):
        try:
            self.handle_api()
        except KeyError:
            self.send(404, {"error": "Job not found"})
        except (ValueError, TypeError, RecursionError, binascii.Error, zipfile.BadZipFile,
                zlib.error, FileExistsError, NotADirectoryError, IsADirectoryError, PermissionError):
            self.send(400, {"error": "Invalid input. Check file names, ZIP contents and upload limits."})
        except (ConnectionError, TimeoutError):
            pass
        except Exception:
            self.send(500, {"error": "Request could not be completed"})

    do_POST = do_GET


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=HERE / "data")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    if os.name == "posix":
        os.umask(0o077)
    mode = os.getenv("NIGHT_SHIFT_MODE", "mock")
    if mode not in ("ollama", "mock"):
        parser.error("Unknown provider mode")
    provider = Mock() if mode == "mock" else Ollama(os.getenv("NIGHT_SHIFT_CONNECTION", ""),
                os.getenv("NIGHT_SHIFT_MODEL", ""), os.getenv("NIGHT_SHIFT_ALLOW_LIVE", ""))
    engine = Engine(args.data, provider)
    engine.start()
    try:
        key = engine.root / "owner-password"
        if not key.exists():
            with key.open("x", encoding="ascii") as f:
                f.write(secrets.token_urlsafe(32))
        password = key.read_text(encoding="ascii").strip()
        if len(password) < 20:
            raise ValueError("Owner password file is invalid")
        with Server(engine, password, args.port) as server:
            print(f"Night Shift ({mode}) http://127.0.0.1:{server.server_port} | Sign in as owner. Password file: {key}", flush=True)
            server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        engine.close()


if __name__ == "__main__":
    main()
