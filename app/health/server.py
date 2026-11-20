import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/health/live", "/healthz"):
            self._send_json(200, {"status": "live"})
            return

        if self.path in ("/health/ready", "/ready"):
            ready = os.getenv(
                "AI_AGENT_READY",
                "true",
            ).lower() in ("1", "true", "yes")
            self._send_json(
                200 if ready else 503,
                {"status": "ready" if ready else "not_ready"},
            )
            return

        if self.path == "/metrics":
            self._send_text(
                200,
                "ai_agent_up 1\n",
                "text/plain; version=0.0.4",
            )
            return

        self._send_json(404, {"error": "not_found"})

    def log_message(self, format, *args):
        return

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(
        self,
        status: int,
        body: str,
        content_type: str,
    ) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(encoded.__len__()))
        self.end_headers()
        self.wfile.write(encoded)


class HealthServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self._server = ThreadingHTTPServer(
            (host, port),
            HealthHandler,
        )
        self._thread: Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = Thread(
            target=self._server.serve_forever,
            name="health-server",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        if self._thread:
            self._thread.join(timeout=5)


def main() -> None:
    host = os.getenv("AI_AGENT_HOST", "0.0.0.0")
    port = int(os.getenv("AI_AGENT_PORT", "8080"))
    server = HealthServer(host=host, port=port)
    stopped = Event()

    server.start()
    try:
        stopped.wait()
    except KeyboardInterrupt:
        server.stop()


if __name__ == "__main__":
    main()
