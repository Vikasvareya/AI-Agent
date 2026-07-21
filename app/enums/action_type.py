from enum import Enum


class ActionType(Enum):
    """
    Represents the action selected by the planner.
    """

    CHAT = "chat"
    TOOL = "tool"