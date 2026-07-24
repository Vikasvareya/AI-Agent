from app.enums.action_type import ActionType
from app.executor.handlers.base_handler import BaseHandler


class ActionRegistry:
    """
    Stores all execution handlers.
    """

    def __init__(self):
        self._handlers: dict[ActionType, BaseHandler] = {}

    def register(
        self,
        action: ActionType,
        handler: BaseHandler,
    ) -> None:
        """
        Register a handler.
        """

        self._handlers[action] = handler

    def get_handler(
        self,
        action: ActionType,
    ) -> BaseHandler | None:
        """
        Return the handler for an action.
        """

        return self._handlers.get(action)