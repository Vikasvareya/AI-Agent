# Model Context Protocol Building Blocks

The repository includes an MCP-style JSON-RPC 2.0 protocol/server and client
building blocks. These are not a complete MCP deployment or coding-agent
integration.

## Supported Methods

- `initialize`
- `tools/list`
- `tools/call`
- `resources/list`
- `resources/read`
- `prompts/list`
- `prompts/get`

## Tool Execution

Tool calls use `ToolManager` as the authoritative registry. MCP tool names and
arguments are forwarded to the registered framework tool.

## Resources

Resources are registered with a URI, name, description, and text content.
No stdio or HTTP transport implementation is included in this repository.
Adding a transport, server registry, tool scopes, timeouts, and audit controls
is future work.

## Errors

The protocol uses JSON-RPC error codes, including:

- `-32600`: Invalid Request
- `-32601`: Method not found
- `-32602`: Invalid params
- `-32603`: Internal/tool execution error
- `-32002`: Resource not found
