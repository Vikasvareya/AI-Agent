from app.memory.base_memory import BaseMemory
from app.planner.base_planner import BasePlanner
from app.executor.base_executor import BaseExecutor



class ChatAgent:
    """
    Main AI Agent.

    Coordinates the conversation flow between
    the user, memory, planner, tools, and AI provider.
    """

    def __init__(
        self,
        memory: BaseMemory,
        planner: BasePlanner,
        executor: BaseExecutor,
    ):
        self.memory = memory
        self.planner = planner
        self.executor = executor
        

    def chat(
        self,
        prompt: str,
    ) -> str:
        """
        Process a user message.
        """

        # Save user message
        self.memory.save(
            "user",
            prompt,
        )

        # Create execution plan
        plan = self.planner.plan(
            prompt,
        )

        # Execute plan
        response = self.executor.execute(
            plan,
        )

        # Save response
        self.memory.save(
            "assistant",
            response,
        )

        return response