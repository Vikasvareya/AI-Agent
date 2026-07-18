from abc import ABC, abstractmethod


class BaseTool(ABC):
    """
    Base class for all AI tools.
    """

    # Unique tool name
    name: str

    # Description shown to the LLM
    description: str

    @abstractmethod
    def run(
        self,
        args: dict,
    ) -> str:
        """
        Execute the tool.

        Args:
            args: Tool arguments.

        Returns:
            Tool result as a string.
        """
        pass