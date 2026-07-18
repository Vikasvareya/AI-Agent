from app.providers.base_provider import BaseProvider
from app.memory.base_memory import BaseMemory
from app.tools.tool_manager import ToolManager


class ChatAgent:
    """
    Main AI Agent.

    It coordinates the conversation between
    the user, memory, and AI provider.

    Coordinates conversations between the user,
    conversation memory, and the AI provider.

    The ChatAgent is responsible for managing the
    conversation flow but delegates storage and
    response generation to other components.
    
    """

    def __init__(
        self,
        provider: BaseProvider,
        memory: BaseMemory,
        tool_manager: ToolManager,
    ):
        self.provider = provider
        self.memory = memory
        self.tool_manager = tool_manager

    def chat(self, prompt: str) -> str:
        # Save user message
        self.memory.save("user", prompt)

        # Load conversation
        messages = self.memory.load(limit=20)


        # Ask AI
        response = self.provider.ask(messages)

        # Save assistant response
        self.memory.save("assistant", response)

        return response