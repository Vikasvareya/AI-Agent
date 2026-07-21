from dataclasses import dataclass, field

from app.enums.action_type import ActionType


@dataclass
class Plan:
    """
    Represents a planner decision.
    """

    action: ActionType
    tool: str | None = None
    args: dict = field(default_factory=dict)