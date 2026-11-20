from collections.abc import Callable
from typing import Any
from uuid import uuid4

from app.mcp.protocol import MCPError


class MCPClient:
    """
    Transport-agnostic MCP JSON-RPC client.

    The transport callable adapts stdio, HTTP, or test sockets.
    """

    def __init__(
        self,
        transport: Callable[[dict], dict],
        *,
        timeout_seconds: float | None = None,
    ):
        if timeout_seconds is not None and timeout_seconds <= 0:
            raise ValueError(
                "MCP timeout must be greater than zero."
            )
        self.transport = transport
        self.timeout_seconds = timeout_seconds

    def request(
        self,
        method: str,
        params: dict | None = None,
    ) -> Any:
        if not method:
            raise ValueError("MCP method cannot be empty.")

        request = {
            "jsonrpc": "2.0",
            "id": str(uuid4()),
            "method": method,
            "params": params or {},
        }
        response = self.transport(request)

        if not isinstance(response, dict):
            raise MCPError(
                -32603,
                "Invalid MCP response",
            )
        if response.get("jsonrpc") != "2.0":
            raise MCPError(
                -32603,
                "Invalid MCP response",
            )
        if "error" in response:
            error = response["error"]
            raise MCPError(
                error.get("code", -32603),
                error.get("message", "MCP request failed"),
                error.get("data"),
            )

        if "result" not in response:
            raise MCPError(
                -32603,
                "MCP response missing result",
            )
        return response["result"]

    def initialize(self) -> dict:
        return self.request(
            "initialize",
            {"protocolVersion": "2025-06-18"},
        )

    def list_tools(self) -> list[dict]:
        return self.request("tools/list").get("tools", [])

    def call_tool(
        self,
        name: str,
        arguments: dict | None = None,
    ) -> dict:
        return self.request(
            "tools/call",
            {
                "name": name,
                "arguments": arguments or {},
            },
        )

    def list_resources(self) -> list[dict]:
        return self.request("resources/list").get("resources", [])

    def read_resource(
        self,
        uri: str,
    ) -> dict:
        return self.request(
            "resources/read",
            {"uri": uri},
        )

    def list_prompts(self) -> list[dict]:
        return self.request("prompts/list").get("prompts", [])

    def get_prompt(
        self,
        name: str,
        arguments: dict | None = None,
    ) -> dict:
        return self.request(
            "prompts/get",
            {
                "name": name,
                "arguments": arguments or {},
            },
        )
