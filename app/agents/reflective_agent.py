from dataclasses import dataclass, field

from app.context.base_context_resolver import BaseContextResolver
from app.executor.base_executor import BaseExecutor
from app.memory.base_memory import BaseMemory
from app.planner.base_planner import BasePlanner


@dataclass
class Reflection:
    attempt: int
    observation: str
    corrected: bool


@dataclass
class ReflectionTrace:
    goal: str
    reflections: list[Reflection] = field(default_factory=list)


class ReflectiveAgent:
    """
    Executes a plan and reflects on failed or unusable observations.
    """

    def __init__(
        self,
        memory: BaseMemory,
        planner: BasePlanner,
        executor: BaseExecutor,
        context_resolver: BaseContextResolver,
        max_corrections: int = 1,
    ):
        self.memory = memory
        self.planner = planner
        self.executor = executor
        self.context_resolver = context_resolver
        self.max_corrections = max(max_corrections, 0)

    def chat(
        self,
        prompt: str,
    ) -> str:
        self.memory.save("user", prompt)
        result, _ = self.run(prompt)
        self.memory.save("assistant", result)
        return result

    def run(
        self,
        prompt: str,
    ) -> tuple[str, ReflectionTrace]:
        resolved_prompt = self.context_resolver.resolve(prompt)
        plan = self.planner.plan(resolved_prompt)
        trace = ReflectionTrace(goal=resolved_prompt)

        for attempt in range(self.max_corrections + 1):
            try:
                result = self.executor.execute(plan)
            except Exception as exc:
                result = str(exc)

            corrected = self._is_usable(result)
            trace.reflections.append(
                Reflection(
                    attempt=attempt + 1,
                    observation=result,
                    corrected=corrected,
                )
            )

            if corrected:
                return result, trace

        return result, trace

    def _is_usable(
        self,
        result: str,
    ) -> bool:
        normalized = result.strip().lower()
        if not normalized:
            return False

        failure_markers = (
            "error",
            "failed",
            "exception",
            "not found",
            "could not",
        )
        return not any(
            marker in normalized
            for marker in failure_markers
        )
