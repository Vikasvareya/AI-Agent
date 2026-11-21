from dataclasses import dataclass, field

from app.context.base_context_resolver import BaseContextResolver
from app.executor.base_executor import BaseExecutor
from app.memory.base_memory import BaseMemory
from app.planner.base_planner import BasePlanner
from app.planner.execution_context import ExecutionContext
from app.planner.execution_plan import ExecutionPlan


@dataclass
class ReActStep:
    thought: str
    action: str
    observation: str


@dataclass
class ReActTrace:
    goal: str
    steps: list[ReActStep] = field(default_factory=list)


class ReActAgent:
    """
    Bounded reasoning loop for a planned request.

    The agent reasons before execution, observes the result, and may retry
    once after an execution failure or invalid tool response.
    """

    def __init__(
        self,
        memory: BaseMemory,
        planner: BasePlanner,
        executor: BaseExecutor,
        context_resolver: BaseContextResolver,
        max_retries: int = 1,
    ):
        self.memory = memory
        self.planner = planner
        self.executor = executor
        self.context_resolver = context_resolver
        self.max_retries = max(max_retries, 0)

    def chat(
        self,
        prompt: str,
    ) -> str:
        self.memory.save(
            "user",
            prompt,
        )

        resolved_prompt = self.context_resolver.resolve(prompt)
        plan = self.planner.plan(resolved_prompt)
        trace = ReActTrace(goal=resolved_prompt)
        context = ExecutionContext()

        final_response = self._run_plan(
            plan,
            context,
            trace,
        )

        self.memory.save(
            "assistant",
            final_response,
        )
        return final_response

    def run(
        self,
        prompt: str,
    ) -> tuple[str, ReActTrace]:
        resolved_prompt = self.context_resolver.resolve(prompt)
        plan = self.planner.plan(resolved_prompt)
        trace = ReActTrace(goal=resolved_prompt)
        final_response = self._run_plan(
            plan,
            ExecutionContext(),
            trace,
        )
        return final_response, trace

    def _run_plan(
        self,
        plan,
        context: ExecutionContext,
        trace: ReActTrace,
    ) -> str:
        if isinstance(plan, ExecutionPlan):
            return self._run_execution_plan(
                plan,
                context,
                trace,
            )

        trace.steps.append(
            ReActStep(
                thought=f"Execute the selected action for '{trace.goal}'.",
                action=plan.action.value,
                observation="",
            )
        )
        for attempt in range(self.max_retries + 1):
            try:
                observation = self.executor.execute(
                    plan,
                    context,
                )
                trace.steps[-1].observation = observation
                return observation
            except Exception as exc:
                trace.steps[-1].observation = str(exc)
                if attempt >= self.max_retries:
                    raise
                trace.steps.append(
                    ReActStep(
                        thought="The action failed; retry with the same bounded plan.",
                        action=plan.action.value,
                        observation=str(exc),
                    )
                )

        raise RuntimeError("ReAct loop ended without a result.")

    def _run_execution_plan(
        self,
        plan: ExecutionPlan,
        context: ExecutionContext,
        trace: ReActTrace,
    ) -> str:
        for step in plan.steps:
            trace.steps.append(
                ReActStep(
                    thought=f"Execute '{step.action.value}' for the current plan.",
                    action=step.action.value,
                    observation="",
                )
            )
        try:
            observation = self.executor.execute(
                plan,
                context,
            )
            if trace.steps:
                trace.steps[-1].observation = observation
            return observation
        except Exception as exc:
            if trace.steps:
                trace.steps[-1].observation = str(exc)
            raise
