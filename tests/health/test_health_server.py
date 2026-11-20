import json
import urllib.error
import urllib.request

from app.health.server import HealthServer


def test_health_endpoints_and_metrics():
    server = HealthServer(
        host="127.0.0.1",
        port=0,
        readiness_checks={
            "database": lambda: True,
            "ollama": lambda: True,
        },
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
            f"http://127.0.0.1:{port}/health/ready",
            timeout=2,
        ) as response:
            payload = json.loads(response.read())
            assert response.status == 200
            assert payload == {
                "status": "ready",
                "dependencies": {
                    "database": "available",
                    "ollama": "available",
                },
            }

        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/metrics",
            timeout=2,
        ) as response:
            assert response.status == 200
            assert b"ai_agent_up 1" in response.read()
    finally:
        server.stop()


def test_ready_endpoint_reports_unavailable_dependencies():
    server = HealthServer(
        host="127.0.0.1",
        port=0,
        readiness_checks={
            "database": lambda: True,
            "ollama": lambda: False,
        },
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
            payload = json.loads(exc.read())
            assert payload == {
                "status": "not_ready",
                "dependencies": {
                    "database": "available",
                    "ollama": "unavailable",
                },
            }
    finally:
        server.stop()
