from app.planner.intents.base_intent import BaseIntent
from app.planner.intents.math_intent import MathIntent
from app.planner.intents.time_intent import TimeIntent


class IntentRegistry:
    """
    Stores all registered intents.
    """

    def __init__(self):
        self._intents: list[BaseIntent] = []

    def register(
        self,
        intent: BaseIntent,
    ) -> None:
        """
        Register an intent.
        """
        self._intents.append(intent)

    def register_default_intents(self) -> None:
        """
        Register built-in intents.
        """
        self.register(MathIntent())
        self.register(TimeIntent())

    def get_matching_intent(
        self,
        prompt: str,
    ) -> BaseIntent | None:
        """
        Return the first matching intent.
        """

        for intent in self._intents:

            print(f"[Registry] Checking {intent.__class__.__name__}")

            if intent.matches(prompt):
                print(f"[Registry] Matched {intent.__class__.__name__}")
                return intent

        print("[Registry] No Intent Matched")
        return None