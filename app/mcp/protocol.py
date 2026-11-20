from dataclasses import dataclass
from typing import Any


class MCPError(Exception):
    def __init__(
        self,
        code: int,
        message: str,
        data: Any = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


@dataclass(frozen=True)
class JSONRPCRequest:
    method: str
    params: dict
    id: Any = None


class MCPProtocol:
    """
    Minimal JSON-RPC 2.0 protocol validation for MCP-style messages.
    """

    def parse_request(
        self,
        message: dict,
    ) -> JSONRPCRequest:
        if not isinstance(message, dict):
            raise MCPError(
                -32600,
                "Invalid Request",
            )
        if message.get("jsonrpc") != "2.0":
            raise MCPError(
                -32600,
                "Invalid Request",
            )

        method = message.get("method")
        if not isinstance(method, str) or not method:
            raise MCPError(
                -32600,
                "Invalid Request",
            )

        params = message.get("params", {})
        if not isinstance(params, dict):
            raise MCPError(
                -32602,
                "Invalid params",
            )

        return JSONRPCRequest(
            method=method,
            params=params,
            id=message.get("id"),
        )

    def success(
        self,
        request_id: Any,
        result: Any,
    ) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        }

    def error(
        self,
        request_id: Any,
        error: MCPError,
    ) -> dict:
        payload = {
            "code": error.code,
            "message": error.message,
        }
        if error.data is not None:
            payload["data"] = error.data

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": payload,
        }
