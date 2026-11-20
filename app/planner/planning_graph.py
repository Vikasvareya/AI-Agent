from app.planner.execution_plan import ExecutionPlan
from app.planner.execution_step import ExecutionStep


class PlanningGraph:
    """
    Directed acyclic graph built from execution steps.
    """

    def __init__(
        self,
        plan: ExecutionPlan,
    ):
        self.plan = plan
        self._steps = {
            step.id: step
            for step in plan.steps
        }

    def validate(self) -> None:
        step_ids = set(
            self._steps
        )

        for step in self._steps.values():
            unknown_dependencies = [
                dependency_id
                for dependency_id in step.dependencies
                if dependency_id not in step_ids
            ]
            if unknown_dependencies:
                raise ValueError(
                    f"Step '{step.id}' has unknown dependencies: "
                    f"{', '.join(unknown_dependencies)}"
                )

        visited: set[str] = set()
        visiting: set[str] = set()

        def visit(step_id: str) -> None:
            if step_id in visiting:
                raise ValueError(
                    "Planning graph contains a dependency cycle."
                )
            if step_id in visited:
                return

            visiting.add(step_id)
            for dependency_id in self._steps[step_id].dependencies:
                visit(dependency_id)
            visiting.remove(step_id)
            visited.add(step_id)

        for step_id in self._steps:
            visit(step_id)

    def topological_levels(self) -> list[list[ExecutionStep]]:
        self.validate()

        remaining = set(
            self._steps
        )
        completed: set[str] = set()
        levels: list[list[ExecutionStep]] = []

        while remaining:
            level = [
                step
                for step in self.plan.steps
                if step.id in remaining
                and set(step.dependencies).issubset(completed)
            ]

            if not level:
                raise ValueError(
                    "Planning graph could not be ordered."
                )

            levels.append(level)
            level_ids = {
                step.id
                for step in level
            }
            remaining -= level_ids
            completed |= level_ids

        return levels

    def predecessors(
        self,
        step_id: str,
    ) -> list[ExecutionStep]:
        if step_id not in self._steps:
            raise KeyError(
                f"Unknown step: '{step_id}'."
            )

        return [
            self._steps[dependency_id]
            for dependency_id in self._steps[step_id].dependencies
        ]

    def successors(
        self,
        step_id: str,
    ) -> list[ExecutionStep]:
        if step_id not in self._steps:
            raise KeyError(
                f"Unknown step: '{step_id}'."
            )

        return [
            step
            for step in self._steps.values()
            if step_id in step.dependencies
        ]
