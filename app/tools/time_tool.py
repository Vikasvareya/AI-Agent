from datetime import datetime

from app.tools.base_tool import BaseTool


class TimeTool(BaseTool):
    """
    Tool for retrieving the current local date and time.
    """

    @property
    def name(self) -> str:
        return "time"

    @property
    def description(self) -> str:
        return "Returns the current local date and time."

    def execute(self, **kwargs) -> str:
        """
        Execute the tool.
        """

        now = datetime.now()

        return now.strftime("%A, %d %B %Y %I:%M:%S %p")