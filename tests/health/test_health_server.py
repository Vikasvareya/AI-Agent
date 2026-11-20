import os
import threading
import urllib.error
import urllib.request

from app.health.server import HealthServer


def test_health_endpoints_and_metrics():
    server = HealthServer(
        host="127.0.0.1",
        port=0,
    )
    server.start()
    port = server._server.server_address[1]

    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/health/live",
            timeout=2,
        ) as response:
            assert response.status == 200
            assert b'"status": "live"' in response.read()

        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/metrics",
            timeout=2,
        ) as response:
            assert response.status == 200
            assert b"ai_agent_up 1" in response.read()
    finally:
        server.stop()


def test_ready_endpoint_can_report_not_ready():
    os.environ["AI_AGENT_READY"] = "false"
    server = HealthServer(
        host="127.0.0.1",
        port=0,
    )
    server.start()
    port = server._server.server_address[1]

    try:
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{port}/health/ready",
                timeout=2,
            )
            assert False, "Expected 503 readiness response"
        except urllib.error.HTTPError as exc:
            assert exc.code == 503
    finally:
        os.environ.pop("AI_AGENT_READY", None)
        server.stop()
