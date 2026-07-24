from app.executor.handlers.base_handler import BaseHandler
from app.memory.base_memory import BaseMemory
from app.models.plan import Plan
from app.providers.base_provider import BaseProvider


class ChatHandler(BaseHandler):
    """
    Executes chat plans.
    """

    def __init__(
        self,
        provider: BaseProvider,
        memory: BaseMemory,
    ):
        self.provider = provider
        self.memory = memory

    def execute(
        self,
        plan: Plan,
    ) -> str:

        messages = self.memory.load(
            limit=20,
        )

        return self.provider.ask(
            messages,
        )