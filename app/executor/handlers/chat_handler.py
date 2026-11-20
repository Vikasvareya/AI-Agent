from app.executor.handlers.base_handler import BaseHandler
from app.memory.base_memory import BaseMemory
from app.models.plan import Plan
from app.providers.base_provider import BaseProvider
from app.memory.rag import RAGPipeline


class ChatHandler(BaseHandler):
    """
    Executes chat plans.
    """

    def __init__(
        self,
        provider: BaseProvider,
        memory: BaseMemory,
        rag: RAGPipeline | None = None,
    ):
        self.provider = provider
        self.memory = memory
        self.rag = rag

    def execute(
        self,
        plan: Plan,
    ) -> str:

        messages = self.memory.load(
            limit=20,
        )

        if self.rag is not None:
            user_messages = [
                message["content"]
                for message in messages
                if message["role"] == "user"
            ]
            if user_messages:
                context = self.rag.build_context(
                    user_messages[-1],
                )
                if context:
                    messages = [
                        {
                            "role": "system",
                            "content": context,
                        },
                        *messages,
                    ]

        return self.provider.ask(
            messages,
        )