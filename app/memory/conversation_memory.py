from app.memory.base_memory import BaseMemory


class ConversationMemory(BaseMemory):
    """
    In-memory conversation storage.

    Stores the conversation as a list of
    role/content dictionaries.
    """

    def __init__(self):
        self.messages: list[dict[str, str]] = []

    def load(
        self,
        limit: int | None = None,
    ) -> list[dict[str, str]]:
        """
        Return the conversation history.

        If a limit is provided, return only the
        most recent messages.
        """

        if limit is not None and limit <= 0:
            return []

        if limit is None:
            return self.messages.copy()

        return self.messages[-limit:]

    def save(
        self,
        role: str,
        content: str,
    ) -> None:
        """
        Save a new message.
        """

        self.messages.append(
            {
                "role": role,
                "content": content,
            }
        )

    def clear(self) -> None:
        """
        Clear the conversation history.
        """

        self.messages.clear()