"""Local-only, stateless workbench server. No user paths or disk writes exposed."""

import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from pydantic import ValidationError

from .catalog import get_example, list_examples
from .models import json_schema
from .render import asset, render_html
from .rules import check_record
from .serialization import MAX_BYTES, dumps, loads, parse


def error_message(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return "\n".join(
            f"{'.'.join(map(str, e['loc'])) or 'ontology'}: {e['msg']}"
            for e in exc.errors(include_url=False, include_input=False)
        )
    return str(exc)


class WorkbenchHandler(BaseHTTPRequestHandler):
    server_version = "EnterpriseOntology/0.1"

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, format, *args):
        # Avoid logging imported text, definitions or records.
        pass

    def allowed(self):
        port = self.server.server_address[1]
        allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if self.headers.get("Host") not in allowed_hosts:
            self.reply(403, {"error": "Local host header required"})
            return False
        origin = self.headers.get("Origin")
        if origin and origin not in {"http://" + host for host in allowed_hosts}:
            self.reply(403, {"error": "Cross-origin requests are not allowed"})
            return False
        return True

    def reply(self, status, data, content_type="application/json; charset=utf-8", nonce=""):
        body = (
            json.dumps(data, ensure_ascii=False, allow_nan=False)
            if content_type.startswith("application/json")
            else data
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            f"default-src 'self'; script-src 'self' 'nonce-{nonce}'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.allowed():
            return
        path = urlsplit(self.path).path
        try:
            if path == "/":
                nonce = secrets.token_urlsafe(20)
                self.reply(
                    200,
                    render_html(get_example("ecommerce"), offline=False, nonce=nonce),
                    "text/html; charset=utf-8",
                    nonce,
                )
            elif path == "/api/health":
                self.reply(200, {"status": "ok", "version": "0.1.0"})
            elif path == "/api/examples":
                self.reply(200, list_examples())
            elif path.startswith("/api/examples/"):
                obj = get_example(path.removeprefix("/api/examples/"))
                self.reply(
                    200,
                    {
                        "ontology": obj.model_dump(mode="json"),
                        "yaml": dumps(obj),
                        "counts": obj.counts(),
                    },
                )
            elif path == "/api/schema":
                self.reply(200, json_schema())
            elif path in ("/assets/style.css", "/assets/app.js"):
                self.reply(
                    200,
                    asset(path.split("/")[-1]),
                    "text/css; charset=utf-8"
                    if path.endswith("css")
                    else "text/javascript; charset=utf-8",
                )
            else:
                self.reply(404, {"error": "Not found"})
        except ValueError as exc:
            self.reply(404, {"error": error_message(exc)})

    def do_POST(self):
        if not self.allowed():
            return
        path = urlsplit(self.path).path
        if path not in ("/api/validate", "/api/render", "/api/check"):
            self.reply(404, {"error": "Not found"})
            return
        if self.headers.get_content_type() != "application/json":
            self.reply(415, {"error": "Content-Type must be application/json"})
            return
        if self.headers.get("Transfer-Encoding"):
            self.reply(400, {"error": "Transfer-Encoding is not supported"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BYTES:
                self.reply(413, {"error": "Request must be between 1 byte and 2 MiB"})
                return
            body = parse(self.rfile.read(length).decode("utf-8"), "json")
            if (
                not isinstance(body, dict)
                or not isinstance(body.get("text"), str)
                or not isinstance(body.get("format", "yaml"), str)
            ):
                raise ValueError("Expected {text: string, format: 'json' | 'yaml'}")
            obj = loads(body["text"], body.get("format", "yaml"))
            if path == "/api/render":
                self.reply(200, render_html(obj), "text/html; charset=utf-8")
            elif path == "/api/check":
                if not isinstance(body.get("entity"), str):
                    raise ValueError("entity must be a string")
                record = body.get("record")
                if "record_text" in body:
                    if not isinstance(body["record_text"], str):
                        raise ValueError("record_text must be a JSON string")
                    record = parse(body["record_text"], "json")
                self.reply(200, check_record(obj, body["entity"], record))
            else:
                self.reply(
                    200,
                    {
                        "ontology": obj.model_dump(mode="json"),
                        "yaml": dumps(obj),
                        "counts": obj.counts(),
                    },
                )
        except (ValueError, UnicodeError, TypeError) as exc:
            self.reply(400, {"error": error_message(exc)})


def make_server(host="127.0.0.1", port=8878):
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError("Workbench is local-only; use 127.0.0.1 or localhost")
    return ThreadingHTTPServer((host, port), WorkbenchHandler)


def serve(host="127.0.0.1", port=8878):
    with make_server(host, port) as server:
        print(
            f"Ontology Workbench: http://{host}:{server.server_address[1]} (Ctrl+C to stop)",
            flush=True,
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
