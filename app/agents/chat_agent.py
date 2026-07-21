from app.providers.base_provider import BaseProvider
from app.memory.base_memory import BaseMemory
from app.tools.tool_manager import ToolManager
from app.planner.base_planner import BasePlanner
from app.enums.action_type import ActionType


class ChatAgent:
    """
    Main AI Agent.

    Coordinates the conversation flow between
    the user, memory, planner, tools, and AI provider.
    """

    def __init__(
        self,
        provider: BaseProvider,
        memory: BaseMemory,
        planner: BasePlanner,
        tool_manager: ToolManager,
    ):
        self.provider = provider
        self.memory = memory
        self.tool_manager = tool_manager
        self.planner = planner
        

    def chat(self, prompt: str) -> str:
        # Save user message
        self.memory.save("user", prompt)

        # Decide what to do
        plan = self.planner.plan(prompt)

        if plan.action is ActionType.TOOL:

            response = self.tool_manager.execute(
                plan.tool,
                plan.args,
            )

        else:

            # Load conversation
            messages = self.memory.load(limit=20)

            # Ask AI
            response = self.provider.ask(messages)

        # Save assistant response
        self.memory.save("assistant", response)

        return response