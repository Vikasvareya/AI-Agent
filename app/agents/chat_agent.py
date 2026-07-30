from app.memory.base_memory import BaseMemory
from app.planner.base_planner import BasePlanner
from app.executor.base_executor import BaseExecutor
from app.context.base_context_resolver import BaseContextResolver


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
        context_resolver: BaseContextResolver,
    ):
        self.memory = memory
        self.planner = planner
        self.executor = executor
        self.context_resolver = context_resolver
        

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
        resolved_prompt = self.context_resolver.resolve(
            prompt,
        )

        plan = self.planner.plan(
            resolved_prompt,
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