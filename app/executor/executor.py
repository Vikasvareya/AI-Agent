import copy
import re

from app.executor.action_registry import ActionRegistry
from app.executor.base_executor import BaseExecutor
from app.models.plan import Plan
from app.planner.enums import PlanStatus, StepStatus
from app.planner.execution_context import ExecutionContext
from app.planner.execution_plan import ExecutionPlan


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
    ) -> str:
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
    ) -> str:
        """
        Execute an ordered set of dependent steps.
        """

        self._validate_plan(plan)

        plan.status = PlanStatus.RUNNING
        previous_result = None
        final_result = ""

        for step in plan.steps:
            step.status = StepStatus.PENDING
            step.result = None

        while any(
            step.status is StepStatus.PENDING
            for step in plan.steps
        ):
            progress_made = False

            for step in plan.steps:
                if step.status is not StepStatus.PENDING:
                    continue

                dependency_statuses = [
                    next(
                        candidate.status
                        for candidate in plan.steps
                        if candidate.id == dependency_id
                    )
                    for dependency_id in step.dependencies
                ]

                if any(
                    status is StepStatus.FAILED
                    or status is StepStatus.SKIPPED
                    for status in dependency_statuses
                ):
                    step.status = StepStatus.SKIPPED
                    progress_made = True
                    continue

                if any(
                    status is not StepStatus.COMPLETED
                    for status in dependency_statuses
                ):
                    continue

                step.status = StepStatus.RUNNING
                progress_made = True

                try:
                    resolved_args = self._resolve_args(
                        copy.deepcopy(step.args),
                        context,
                        previous_result,
                    )
                    tool = resolved_args.pop(
                        "tool",
                        None,
                    )

                    handler = self.registry.get_handler(
                        step.action,
                    )
                    if handler is None:
                        raise ValueError(
                            f"No handler registered for action: {step.action}"
                        )

                    step_plan = Plan(
                        action=step.action,
                        tool=tool,
                        args=resolved_args,
                    )
                    step_result = handler.execute(
                        step_plan,
                    )

                    step.result = step_result
                    step.status = StepStatus.COMPLETED
                    context.results[step.id] = step_result
                    previous_result = step_result
                    final_result = step_result

                except Exception as exc:
                    step.result = str(exc)
                    step.status = StepStatus.FAILED
                    plan.status = PlanStatus.FAILED
                    raise

            if not progress_made:
                raise ValueError(
                    "Execution plan contains unresolved step dependencies."
                )

        plan.status = PlanStatus.COMPLETED
        return str(final_result)

    def _validate_plan(
        self,
        plan: ExecutionPlan,
    ) -> None:
        step_ids = {
            step.id
            for step in plan.steps
        }

        for step in plan.steps:
            for dependency_id in step.dependencies:
                if dependency_id not in step_ids:
                    plan.status = PlanStatus.FAILED
                    raise ValueError(
                        f"Step '{step.id}' depends on unknown step "
                        f"'{dependency_id}'."
                    )

        if not plan.steps:
            plan.status = PlanStatus.COMPLETED
            return

        completed_or_skipped: set[str] = set()
        remaining = {
            step.id
            for step in plan.steps
        }

        while remaining:
            ready = {
                step.id
                for step in plan.steps
                if step.id in remaining
                and set(step.dependencies).issubset(completed_or_skipped)
            }
            if not ready:
                plan.status = PlanStatus.FAILED
                raise ValueError(
                    "Execution plan contains a dependency cycle."
                )

            remaining -= ready
            completed_or_skipped |= ready

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

        if len(matches) == 1 and value.strip() == f"{{{{{matches[0].strip()}}}}}":
            return self._resolve_reference(
                matches[0].strip(),
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

        if name in context.variables:
            return context.variables[name]

        if name in context.results:
            return context.results[name]

        raise ValueError(
            f"Unknown execution reference: '{name}'."
        )