from app.executor.action_registry import ActionRegistry
from app.executor.base_executor import BaseExecutor
from app.models.plan import Plan


class Executor(BaseExecutor):
    """
    Executes plans using registered handlers.
    """

    def __init__(
        self,
        registry: ActionRegistry,
    ):
        self.registry = registry

    def execute(
        self,
        plan: Plan,
    ) -> str:
        """
        Execute a plan.
        """

        handler = self.registry.get_handler(
            plan.action,
        )

        if handler is None:
            raise ValueError(
                f"No handler registered for action: {plan.action}"
            )

        return handler.execute(
            plan,
        )