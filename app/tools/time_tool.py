import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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

        clarification = kwargs.get("clarification")
        if isinstance(clarification, str) and clarification.strip():
            return clarification

        timezone_name = kwargs.get("timezone") or os.getenv(
            "AI_AGENT_TIMEZONE",
        )
        if timezone_name:
            if not isinstance(timezone_name, str):
                raise ValueError("Timezone must be a string.")
            try:
                timezone = ZoneInfo(timezone_name)
            except (ZoneInfoNotFoundError, ValueError) as exc:
                raise ValueError(
                    f"Unknown IANA timezone: '{timezone_name}'."
                ) from exc
            now = datetime.now(timezone)
        else:
            now = datetime.now().astimezone()

        offset = kwargs.get("offset_days", 0)
        if isinstance(offset, bool) or not isinstance(offset, int):
            raise ValueError("offset_days must be an integer.")
        if offset:
            now = now + timedelta(days=offset)

        formatted = now.strftime("%A, %d %B %Y %I:%M:%S %p %Z")
        location = kwargs.get("location")
        if isinstance(location, str) and location.strip():
            return f"Current time in {location}: {formatted}"
        return formatted