import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status: int, payload: dict[str, object]) -> None:
        content = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:  # noqa: N802 - nom imposé par BaseHTTPRequestHandler
        if self.path == "/api/v1/health":
            api_key = self.headers.get("X-API-Key")
            if api_key != "smoke-api-key":
                self.send_json(401, {"code": "missing_api_key"})
                return
            self.send_json(200, {"path": self.path, "api_key": api_key})
            return
        if self.path == "/api/v1/unauthorized":
            self.send_json(401, {"code": "invalid_api_key"})
            return
        self.send_json(404, {"code": "not_found", "path": self.path})

    def log_message(self, *_arguments: object) -> None:
        return


ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
