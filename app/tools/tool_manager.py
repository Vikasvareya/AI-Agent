from app.tools.base_tool import BaseTool


class ToolManager:
    """
    Manages all available tools.
    """

    def __init__(self):
        self.tools: dict[str, BaseTool] = {}

    def register(
        self,
        tool: BaseTool,
    ) -> None:
        """
        Register a new tool.
        """

        if tool.name in self.tools:
            raise ValueError(
                f"Tool '{tool.name}' is already registered."
            )

        self.tools[tool.name] = tool

    def get(
        self,
        name: str,
    ) -> BaseTool | None:
        """
        Return a tool by name.
        """

        return self.tools.get(name)

    def execute(
        self,
        name: str,
        args: dict,
    ) -> str:
        """
        Execute a registered tool.
        """

        tool = self.get(name)

        if tool is None:
            return f"Tool '{name}' not found."

        return tool.run(args)