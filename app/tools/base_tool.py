from abc import ABC, abstractmethod


class BaseTool(ABC):
    """
    Base class for all AI tools.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique tool name.
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """
        Human-readable description of the tool.
        """
        pass

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """
        Execute the tool.

        Args:
            **kwargs: Tool-specific arguments.

        Returns:
            Tool result as a string.
        """
        pass