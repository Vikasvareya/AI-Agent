import json
import urllib.request

from app.api.http_server import WorkflowHTTPServer
from app.api.server_main import create_demo_api
from app.realtime.event_bus import EventBus


def test_dashboard_and_demo_workflow_listing():
    api, bus = create_demo_api()
    server = WorkflowHTTPServer(
        api,
        bus,
        host="127.0.0.1",
        port=0,
    )
    server.start()
    port = server._server.server_address[1]

    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/",
            timeout=2,
        ) as response:
            html = response.read().decode("utf-8")
            assert response.status == 200
            assert "AI Agent Control Plane" in html

        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/v1/workflows",
            timeout=2,
        ) as response:
            payload = json.loads(response.read())
            assert payload["workflows"][0]["name"] == "Demo Approval Workflow"
    finally:
        server.stop()
