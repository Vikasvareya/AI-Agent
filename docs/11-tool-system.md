# Tool System

Tools implement the framework tool interface and are registered with the
`ToolManager`. The current built-in examples include calculator and time
tools; plugin discovery can contribute tools through the plugin interface.

The tool registry is a framework capability, not a safe sandbox. Tool
implementations execute in-process. The coding workspace does not currently
invoke these tools, plugins, shell commands, or MCP servers.

Any future external or privileged tool integration needs explicit
authorization, argument validation, timeouts, audit, isolation, and revocation.
See [Security and Governance](./SECURITY_AND_GOVERNANCE.md).
