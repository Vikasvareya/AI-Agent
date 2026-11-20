from app.mcp.protocol import MCPProtocol
from app.mcp.server import MCPServer
from app.mcp.client import MCPClient
from app.tools.base_tool import BaseTool
from app.tools.tool_manager import ToolManager


class EchoTool(BaseTool):
    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echo a text value"

    def execute(self, **kwargs) -> str:
        return str(kwargs.get("text", ""))


def test_mcp_initialize_and_list_tools():
    manager = ToolManager()
    manager.register(EchoTool())
    server = MCPServer(manager)

    initialized = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-06-18"},
        }
    )
    listed = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
    )

    assert initialized["result"]["serverInfo"]["name"] == "ai-agent-framework"
    assert listed["result"]["tools"][0]["name"] == "echo"


def test_mcp_calls_registered_tool():
    manager = ToolManager()
    manager.register(EchoTool())
    server = MCPServer(manager)

    response = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "echo",
                "arguments": {"text": "hello"},
            },
        }
    )

    assert response["result"]["content"][0]["text"] == "hello"
    assert response["result"]["isError"] is False


def test_mcp_resources_list_and_read():
    manager = ToolManager()
    server = MCPServer(manager)
    server.register_resource(
        "memory://preferences",
        name="Preferences",
        description="User preferences",
        content="Prefer concise answers.",
    )

    listed = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "resources/list",
            "params": {},
        }
    )
    read = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "resources/read",
            "params": {"uri": "memory://preferences"},
        }
    )

    assert listed["result"]["resources"][0]["uri"] == "memory://preferences"
    assert read["result"]["contents"][0]["text"] == "Prefer concise answers."


def test_mcp_rejects_unknown_method():
    server = MCPServer(ToolManager())

    response = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "unknown/method",
            "params": {},
        }
    )

    assert response["error"]["code"] == -32601


def test_mcp_protocol_rejects_invalid_request():
    protocol = MCPProtocol()

    try:
        protocol.parse_request(
            {
                "jsonrpc": "1.0",
                "method": "initialize",
            }
        )
        assert False, "Expected invalid JSON-RPC request"
    except Exception as exc:
        assert getattr(exc, "code", None) == -32600


def test_mcp_client_uses_transport_round_trip():
    manager = ToolManager()
    manager.register(EchoTool())
    server = MCPServer(manager)
    client = MCPClient(server.handle)

    initialized = client.initialize()
    tools = client.list_tools()
    called = client.call_tool(
        "echo",
        {"text": "client-result"},
    )

    assert initialized["serverInfo"]["name"] == "ai-agent-framework"
    assert tools[0]["name"] == "echo"
    assert called["content"][0]["text"] == "client-result"


def test_mcp_prompts_register_list_and_render():
    server = MCPServer(ToolManager())
    server.register_prompt(
        "summarize",
        description="Summarize a topic",
        arguments=[
            {"name": "topic", "required": True},
        ],
        template="Summarize {topic} in five bullets.",
    )

    listed = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "prompts/list",
            "params": {},
        }
    )
    rendered = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "prompts/get",
            "params": {
                "name": "summarize",
                "arguments": {"topic": "Python"},
            },
        }
    )

    assert listed["result"]["prompts"][0]["name"] == "summarize"
    assert rendered["result"]["messages"][0]["content"]["text"].startswith(
        "Summarize Python"
    )


def test_mcp_authorization_and_tool_allowlist():
    manager = ToolManager()
    manager.register(EchoTool())
    server = MCPServer(
        manager,
        auth_token="secret",
        allowed_tools={"echo"},
    )

    unauthorized = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "tools/list",
            "params": {},
        }
    )
    authorized = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "__auth_token": "secret",
                "name": "echo",
                "arguments": {"text": "ok"},
            },
        }
    )

    assert unauthorized["error"]["code"] == -32001
    assert authorized["result"]["content"][0]["text"] == "ok"
