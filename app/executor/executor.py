import copy
import re
from threading import Lock

from app.executor.action_registry import ActionRegistry
from app.executor.base_executor import BaseExecutor
from app.models.plan import Plan
from app.planner.enums import PlanStatus, StepStatus
from app.planner.execution_context import ExecutionContext
from app.planner.execution_plan import ExecutionPlan
from app.planner.planning_graph import PlanningGraph


_PLAN_EXECUTION_LOCKS: dict[int, Lock] = {}
_PLAN_EXECUTION_LOCKS_GUARD = Lock()


class Executor(BaseExecutor):
    """
    Executes plans using registered handlers.
    """

    def __init__(
        self,
        registry: ActionRegistry,
    ):
        self.registry = registry

    def execute(
        self,
        plan: Plan | ExecutionPlan,
        context: ExecutionContext | None = None,
    ) -> object:
        """
        Execute a plan.
        """

        if isinstance(plan, ExecutionPlan):
            return self.execute_plan(
                plan,
                context or ExecutionContext(),
            )

        handler = self.registry.get_handler(
            plan.action,
        )

        if handler is None:
            raise ValueError(
                f"No handler registered for action: {plan.action}"
            )

        return handler.execute(
            plan,
        )

    def execute_plan(
        self,
        plan: ExecutionPlan,
        context: ExecutionContext,
    ) -> object:
        """
        Execute an ordered set of dependent steps.
        """
        lock = self._get_plan_lock(plan)
        if not lock.acquire(blocking=False):
            raise RuntimeError(
                f"Execution plan '{plan.id}' is already RUNNING."
            )

        try:
            if plan.status is PlanStatus.RUNNING:
                raise RuntimeError(
                    f"Execution plan '{plan.id}' is already RUNNING."
                )
            if plan.status is PlanStatus.COMPLETED:
                raise ValueError(
                    f"Execution plan '{plan.id}' has already completed "
                    "and cannot execute again."
                )
            if plan.status is PlanStatus.FAILED:
                raise ValueError(
                    f"Execution plan '{plan.id}' is in FAILED state "
                    "and cannot replay automatically."
                )
            if any(
                step.status is not StepStatus.PENDING
                for step in plan.steps
            ):
                raise ValueError(
                    f"Execution plan '{plan.id}' has partially executed "
                    "and cannot replay automatically."
                )

            graph = PlanningGraph(plan)
            try:
                graph.validate()
            except Exception:
                plan.status = PlanStatus.FAILED
                raise

            if not plan.steps:
                plan.status = PlanStatus.COMPLETED
                return ""

            plan.status = PlanStatus.RUNNING
            previous_result = None
            final_result = ""
            ordered_steps = [
                step
                for level in graph.topological_levels()
                for step in level
            ]

            for step in ordered_steps:
                step.status = StepStatus.RUNNING
                try:
                    resolved_args = self._resolve_args(
                        copy.deepcopy(step.args),
                        context,
                        previous_result,
                    )
                    tool = resolved_args.pop("tool", None)
                    handler = self.registry.get_handler(step.action)
                    if handler is None:
                        raise ValueError(
                            f"No handler registered for action: {step.action}"
                        )

                    step_plan = Plan(
                        action=step.action,
                        tool=tool,
                        args=resolved_args,
                    )
                    step_result = handler.execute(step_plan)
                    step.result = step_result
                    step.status = StepStatus.COMPLETED
                    context.results[step.id] = step_result
                    previous_result = step_result
                    final_result = step_result
                except Exception as exc:
                    step.result = str(exc)
                    step.status = StepStatus.FAILED
                    plan.status = PlanStatus.FAILED
                    for unexecuted in plan.steps:
                        if unexecuted.status is StepStatus.PENDING:
                            unexecuted.status = StepStatus.SKIPPED
                    raise

            plan.status = PlanStatus.COMPLETED
            return final_result
        finally:
            lock.release()
            with _PLAN_EXECUTION_LOCKS_GUARD:
                _PLAN_EXECUTION_LOCKS.pop(id(plan), None)

    def _validate_plan(
        self,
        plan: ExecutionPlan,
    ) -> None:
        try:
            PlanningGraph(plan).validate()
        except Exception:
            plan.status = PlanStatus.FAILED
            raise

    def _get_plan_lock(self, plan: ExecutionPlan) -> Lock:
        plan_key = id(plan)
        with _PLAN_EXECUTION_LOCKS_GUARD:
            lock = _PLAN_EXECUTION_LOCKS.get(plan_key)
            if lock is None:
                lock = Lock()
                _PLAN_EXECUTION_LOCKS[plan_key] = lock
            return lock

    def _resolve_args(
        self,
        value,
        context: ExecutionContext,
        previous_result,
    ):
        if isinstance(value, dict):
            return {
                key: self._resolve_args(
                    item,
                    context,
                    previous_result,
                )
                for key, item in value.items()
            }

        if isinstance(value, list):
            return [
                self._resolve_args(
                    item,
                    context,
                    previous_result,
                )
                for item in value
            ]

        if not isinstance(value, str):
            return value

        pattern = re.compile(r"\{\{\s*([^{}]+)\s*\}\}")
        matches = pattern.findall(value)

        if not matches:
            return value

        exact_match = re.fullmatch(
            r"\{\{\s*([^{}]+?)\s*\}\}",
            value.strip(),
        )
        if len(matches) == 1 and exact_match:
            return self._resolve_reference(
                exact_match.group(1).strip(),
                context,
                previous_result,
            )

        def replace(match):
            resolved = self._resolve_reference(
                match.group(1).strip(),
                context,
                previous_result,
            )
            return str(resolved)

        return pattern.sub(
            replace,
            value,
        )

    def _resolve_reference(
        self,
        name: str,
        context: ExecutionContext,
        previous_result,
    ):
        if name == "previous":
            if previous_result is None:
                raise ValueError(
                    "Cannot reference '{{previous}}' before any step has completed."
                )
            return previous_result

        normalized = name.strip()
        if normalized.startswith("context."):
            normalized = normalized[len("context."):]

        if normalized.startswith("variables"):
            return self._resolve_dotted_value(
                normalized[len("variables"):].lstrip("."),
                context.variables,
                normalized,
            )
        if normalized.startswith("results"):
            return self._resolve_dotted_value(
                normalized[len("results"):].lstrip("."),
                context.results,
                normalized,
            )
        first_segment = re.split(r"[.\[]", name, maxsplit=1)[0]
        if first_segment in context.variables:
            return self._resolve_dotted_value(
                name,
                context.variables,
                name,
            )
        if first_segment in context.results:
            return self._resolve_dotted_value(
                name,
                context.results,
                name,
            )

        raise ValueError(
            f"Unknown execution reference: '{name}'."
        )

    def _resolve_dotted_value(
        self,
        path: str,
        root,
        reference: str,
    ):
        if not path:
            return root

        current = root
        parts = re.findall(r"[^.\[\]]+|\[(?:\d+)\]", path)
        for part in parts:
            if part.startswith("[") and part.endswith("]"):
                index = int(part[1:-1])
                if not isinstance(current, list) or index >= len(current):
                    raise ValueError(
                        f"Unknown execution reference: '{reference}'."
                    )
                current = current[index]
                continue
            if isinstance(current, dict) and part in current:
                current = current[part]
                continue
            raise ValueError(
                f"Unknown execution reference: '{reference}'."
            )
        return current