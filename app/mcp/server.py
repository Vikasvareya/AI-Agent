from app.mcp.protocol import (
    MCPError,
    MCPProtocol,
)
from app.tools.tool_manager import ToolManager


class MCPServer:
    """
    MCP-style JSON-RPC server that exposes framework tools.
    """

    SERVER_NAME = "ai-agent-framework"
    SERVER_VERSION = "0.2.0"

    def __init__(
        self,
        tool_manager: ToolManager,
        *,
        auth_token: str | None = None,
        allowed_tools: set[str] | None = None,
        allowed_resources: set[str] | None = None,
    ):
        self.tool_manager = tool_manager
        self.protocol = MCPProtocol()
        self._resources: dict[str, dict] = {}
        self._prompts: dict[str, dict] = {}
        self.auth_token = auth_token
        self.allowed_tools = allowed_tools
        self.allowed_resources = allowed_resources

    def register_resource(
        self,
        uri: str,
        *,
        name: str,
        description: str = "",
        content: str = "",
    ) -> None:
        if not uri or not name:
            raise ValueError(
                "MCP resource uri and name are required."
            )
        self._resources[uri] = {
            "uri": uri,
            "name": name,
            "description": description,
            "content": content,
        }

    def register_prompt(
        self,
        name: str,
        *,
        description: str = "",
        arguments: list[dict] | None = None,
        template: str = "",
    ) -> None:
        if not name:
            raise ValueError("MCP prompt name is required.")
        self._prompts[name] = {
            "name": name,
            "description": description,
            "arguments": arguments or [],
            "template": template,
        }

    def _authorize(
        self,
        params: dict,
    ) -> bool:
        if self.auth_token is None:
            return True
        return params.pop(
            "__auth_token",
            None,
        ) == self.auth_token

    def handle(
        self,
        message: dict,
    ) -> dict:
        request_id = message.get("id") if isinstance(message, dict) else None

        try:
            request = self.protocol.parse_request(message)
            if not self._authorize(request.params):
                raise MCPError(
                    -32001,
                    "Unauthorized",
                )
            if request.method == "initialize":
                result = self._initialize(request.params)
            elif request.method == "tools/list":
                result = self._list_tools()
            elif request.method == "tools/call":
                result = self._call_tool(request.params)
            elif request.method == "resources/list":
                result = self._list_resources()
            elif request.method == "resources/read":
                result = self._read_resource(request.params)
            elif request.method == "prompts/list":
                result = self._list_prompts()
            elif request.method == "prompts/get":
                result = self._get_prompt(request.params)
            else:
                raise MCPError(
                    -32601,
                    "Method not found",
                )
            return self.protocol.success(
                request.id,
                result,
            )
        except MCPError as exc:
            return self.protocol.error(
                request_id,
                exc,
            )
        except Exception as exc:
            return self.protocol.error(
                request_id,
                MCPError(
                    -32603,
                    "Internal error",
                    str(exc),
                ),
            )

    def _initialize(
        self,
        params: dict,
    ) -> dict:
        return {
            "protocolVersion": params.get(
                "protocolVersion",
                "2025-06-18",
            ),
            "serverInfo": {
                "name": self.SERVER_NAME,
                "version": self.SERVER_VERSION,
            },
            "capabilities": {
                "tools": {},
                "resources": {},
                "prompts": {},
            },
        }

    def _list_tools(
        self,
    ) -> dict:
        tools = []
        for tool in self.tool_manager.tools.values():
            tools.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": {
                        "type": "object",
                        "additionalProperties": True,
                    },
                }
            )
        return {"tools": tools}

    def _call_tool(
        self,
        params: dict,
    ) -> dict:
        name = params.get("name")
        arguments = params.get(
            "arguments",
            {},
        )

        if not isinstance(name, str) or not name:
            raise MCPError(
                -32602,
                "Invalid params",
                "Tool name is required.",
            )
        if not isinstance(arguments, dict):
            raise MCPError(
                -32602,
                "Invalid params",
                "Tool arguments must be an object.",
            )
        if name not in self.tool_manager.tools:
            raise MCPError(
                -32602,
                "Invalid params",
                f"Tool '{name}' was not found.",
            )
        if (
            self.allowed_tools is not None
            and name not in self.allowed_tools
        ):
            raise MCPError(
                -32001,
                "Unauthorized",
                f"Tool '{name}' is not allowed.",
            )

        try:
            content = self.tool_manager.execute(
                name,
                arguments,
            )
        except Exception as exc:
            raise MCPError(
                -32603,
                "Tool execution failed",
                str(exc),
            ) from exc

        return {
            "content": [
                {
                    "type": "text",
                    "text": str(content),
                }
            ],
            "isError": False,
        }

    def _list_resources(
        self,
    ) -> dict:
        return {
            "resources": [
                {
                    "uri": resource["uri"],
                    "name": resource["name"],
                    "description": resource["description"],
                }
                for resource in self._resources.values()
            ]
        }

    def _read_resource(
        self,
        params: dict,
    ) -> dict:
        uri = params.get("uri")
        if not isinstance(uri, str) or uri not in self._resources:
            raise MCPError(
                -32002,
                "Resource not found",
                uri,
            )
        if (
            self.allowed_resources is not None
            and uri not in self.allowed_resources
        ):
            raise MCPError(
                -32001,
                "Unauthorized",
                f"Resource '{uri}' is not allowed.",
            )

        resource = self._resources[uri]
        return {
            "contents": [
                {
                    "uri": resource["uri"],
                    "mimeType": "text/plain",
                    "text": resource["content"],
                }
            ]
        }

    def _list_prompts(
        self,
    ) -> dict:
        return {
            "prompts": [
                {
                    "name": prompt["name"],
                    "description": prompt["description"],
                    "arguments": prompt["arguments"],
                }
                for prompt in self._prompts.values()
            ]
        }

    def _get_prompt(
        self,
        params: dict,
    ) -> dict:
        name = params.get("name")
        if not isinstance(name, str) or name not in self._prompts:
            raise MCPError(
                -32602,
                "Invalid params",
                f"Prompt '{name}' was not found.",
            )

        prompt = self._prompts[name]
        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            raise MCPError(
                -32602,
                "Invalid params",
                "Prompt arguments must be an object.",
            )

        text = prompt["template"]
        for key, value in arguments.items():
            text = text.replace(
                "{" + str(key) + "}",
                str(value),
            )

        return {
            "description": prompt["description"],
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": text,
                    },
                }
            ],
        }
