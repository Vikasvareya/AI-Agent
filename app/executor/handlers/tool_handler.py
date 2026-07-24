from app.executor.handlers.base_handler import BaseHandler
from app.models.plan import Plan
from app.tools.tool_manager import ToolManager


class ToolHandler(BaseHandler):
    """
    Executes tool plans.
    """

    def __init__(
        self,
        tool_manager: ToolManager,
    ):
        self.tool_manager = tool_manager

    def execute(
        self,
        plan: Plan,
    ) -> str:

        return self.tool_manager.execute(
            plan.tool,
            plan.args,
        )