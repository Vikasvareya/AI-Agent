from dataclasses import dataclass


@dataclass
class ConversationContext:
    """
    Stores the current conversational context.

    This class only stores state.
    It contains no business logic.
    """

    last_entity: str | None = None
    last_file: str | None = None
    last_tool: str | None = None
    last_location: str | None = None