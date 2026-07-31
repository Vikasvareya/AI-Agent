from abc import ABC, abstractmethod

from app.planner.intents.base_intent import BaseIntent
from app.tools.base_tool import BaseTool


class BasePlugin(ABC):
    """
    Base class for all framework plugins.
    """

    @abstractmethod
    def get_intents(self) -> list[BaseIntent]:
        """
        Return planner intents provided by this plugin.
        """
        pass

    @abstractmethod
    def get_tools(self) -> list[BaseTool]:
        """
        Return tools provided by this plugin.
        """
        pass