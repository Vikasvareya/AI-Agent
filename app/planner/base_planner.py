from abc import ABC, abstractmethod


class BasePlanner(ABC):
    """
    Base planner responsible for deciding
    what action the AI Agent should take.
    """

    @abstractmethod
    def plan(
        self,
        prompt: str,
    ) -> dict:
        """
        Decide the next action.

        Returns:
            A dictionary describing the action.
        """
        pass