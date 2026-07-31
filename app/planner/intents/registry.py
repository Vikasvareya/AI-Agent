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
        Return the highest-ranked matching intent.
        """

        candidates: list[tuple[BaseIntent, float, int]] = []

        for intent in self._intents:

            print(f"[Registry] Checking {intent.__class__.__name__}")

            match = intent.matches(prompt)

            if match.matched:

                print(
                    f"[Registry] Matched {intent.__class__.__name__} "
                    f"(priority={match.priority}, confidence={match.confidence})"
                )

                candidates.append(
                    (
                        intent,
                        match.confidence,
                        match.priority,
                    )
                )

        if not candidates:

            print("[Registry] No Intent Matched")

            return None

        candidates.sort(
            key=lambda item: (
                item[2],  # priority
                item[1],  # confidence
            ),
            reverse=True,
        )

        winner = candidates[0][0]

        print(
            f"[Registry] Selected {winner.__class__.__name__}"
        )

        return winner