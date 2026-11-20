from concurrent.futures import (
    Future,
    ThreadPoolExecutor,
    TimeoutError as FuturesTimeoutError,
)
from threading import Lock
from time import perf_counter
from typing import Callable

from app.workflows.models import (
    ApprovalStatus,
    NodeStatus,
    Workflow,
    WorkflowNode,
    WorkflowRun,
    WorkflowStatus,
)


class WorkflowEngine:
    """
    Thread-safe, in-process DAG workflow engine.

    Independent workflow nodes execute concurrently within topological levels.
    Nodes with dependencies execute only after all dependencies succeed.
    """

    def __init__(
        self,
        max_workers: int = 8,
        checkpoint_callback: Callable[[WorkflowRun], None] | None = None,
        event_bus=None,
        tracing=None,
        metrics=None,
    ):
        if max_workers <= 0:
            raise ValueError("max_workers must be greater than zero.")

        self.max_workers = max_workers
        self.checkpoint_callback = checkpoint_callback
        self.event_bus = event_bus
        self.tracing = tracing
        self.metrics = metrics
        self._runs: dict[str, WorkflowRun] = {}
        self._idempotency: dict[str, str] = {}
        self._cancelled: set[str] = set()
        self._workflows: dict[str, Workflow] = {}
        self._contexts: dict[str, dict] = {}
        self._lock = Lock()

    def start(
        self,
        workflow: Workflow,
        *,
        idempotency_key: str | None = None,
        initial_context: dict | None = None,
        owner_id: str | None = None,
    ) -> WorkflowRun:
        self._validate(workflow)
        levels = self._topological_levels(workflow)

        with self._lock:
            if idempotency_key:
                existing_run_id = self._idempotency.get(idempotency_key)
                if existing_run_id:
                    return self._runs[existing_run_id]

            run = WorkflowRun(
                workflow_id=workflow.id,
                idempotency_key=idempotency_key,
                node_statuses={
                    node.name: NodeStatus.PENDING
                    for node in workflow.nodes
                },
                owner_id=owner_id,
                initial_context=dict(initial_context or {}),
            )
            self._runs[run.id] = run
            self._workflows[run.id] = workflow
            self._contexts[run.id] = dict(run.initial_context)
            if idempotency_key:
                self._idempotency[idempotency_key] = run.id

        context = dict(initial_context or {})
        run.status = WorkflowStatus.RUNNING
        workflow_span = None
        workflow_started = perf_counter()
        if self.tracing:
            workflow_span = self.tracing.start_span(
                "workflow.run",
                attributes={
                    "run_id": run.id,
                    "workflow_id": workflow.id,
                },
            )
        if self.metrics:
            self.metrics.increment(
                "workflow_runs_started",
                labels={"workflow_id": workflow.id},
            )
        self._checkpoint(run)

        try:
            for level in levels:
                if run.id in self._cancelled:
                    run.status = WorkflowStatus.CANCELLED
                    self._checkpoint(run)
                    return run

                self._execute_level(
                    workflow,
                    level,
                    run,
                    context,
                )

                waiting_for_approval = any(
                    status is NodeStatus.WAITING_APPROVAL
                    for status in run.node_statuses.values()
                )
                if waiting_for_approval:
                    run.status = WorkflowStatus.WAITING_APPROVAL
                    self._checkpoint(run)
                    return run

                if any(
                    status is NodeStatus.FAILED
                    for status in run.node_statuses.values()
                ):
                    run.status = WorkflowStatus.FAILED
                    if self.tracing and workflow_span:
                        self.tracing.end_span(
                            workflow_span,
                            status="error",
                            attributes={"error": "node_failed"},
                        )
                    if self.metrics:
                        self.metrics.increment(
                            "workflow_runs_failed",
                            labels={"workflow_id": workflow.id},
                        )
                        self.metrics.observe(
                            "workflow_duration",
                            perf_counter() - workflow_started,
                            labels={"workflow_id": workflow.id},
                        )
                    self._checkpoint(run)
                    return run

            run.status = WorkflowStatus.COMPLETED
            if self.tracing and workflow_span:
                self.tracing.end_span(
                    workflow_span,
                    status="ok",
                )
            if self.metrics:
                self.metrics.increment(
                    "workflow_runs_completed",
                    labels={"workflow_id": workflow.id},
                )
                self.metrics.observe(
                    "workflow_duration",
                    perf_counter() - workflow_started,
                    labels={"workflow_id": workflow.id},
                )
            self._checkpoint(run)
            return run

        except Exception as exc:
            run.status = WorkflowStatus.FAILED
            run.errors["workflow"] = str(exc)
            if self.tracing and workflow_span:
                self.tracing.end_span(
                    workflow_span,
                    status="error",
                    attributes={"error": str(exc)},
                )
            if self.metrics:
                self.metrics.increment(
                    "workflow_runs_failed",
                    labels={"workflow_id": workflow.id},
                )
                self.metrics.observe(
                    "workflow_duration",
                    perf_counter() - workflow_started,
                    labels={"workflow_id": workflow.id},
                )
            self._checkpoint(run)
            return run

    def restore_run(
        self,
        workflow: Workflow,
        run: WorkflowRun,
    ) -> WorkflowRun:
        if run.workflow_id != workflow.id:
            raise ValueError(
                "Workflow run references a different workflow definition."
            )
        self._validate(workflow)
        self._topological_levels(workflow)

        interrupted = run.status in (
            WorkflowStatus.PENDING,
            WorkflowStatus.RUNNING,
        )
        if interrupted:
            run.status = WorkflowStatus.FAILED
            run.errors.setdefault(
                "workflow",
                "Workflow run was interrupted by a process restart.",
            )
            for node_name, status in run.node_statuses.items():
                if status is NodeStatus.RUNNING:
                    run.node_statuses[node_name] = NodeStatus.FAILED
                    run.errors.setdefault(
                        node_name,
                        "Workflow node was interrupted by a process restart.",
                    )

        with self._lock:
            if run.id in self._runs:
                raise ValueError(
                    f"Workflow run '{run.id}' is already loaded."
                )
            if run.idempotency_key:
                existing_id = self._idempotency.get(
                    run.idempotency_key
                )
                if existing_id and existing_id != run.id:
                    raise ValueError(
                        "Persisted workflow runs contain a duplicate "
                        "idempotency key."
                    )
                self._idempotency[run.idempotency_key] = run.id
            self._runs[run.id] = run
            self._workflows[run.id] = workflow
            self._contexts[run.id] = {
                **run.initial_context,
                **run.results,
            }
            if run.status is WorkflowStatus.CANCELLED:
                self._cancelled.add(run.id)

        if interrupted:
            self._checkpoint(run)
        return run

    def get_run(
        self,
        run_id: str,
    ) -> WorkflowRun | None:
        with self._lock:
            return self._runs.get(run_id)

    def list_runs(self) -> list[WorkflowRun]:
        with self._lock:
            return list(self._runs.values())

    def approve(
        self,
        run_id: str,
        node_name: str,
        *,
        approved: bool,
        approver: str,
    ) -> WorkflowRun:
        if not approver.strip():
            raise ValueError("Approver identity cannot be empty.")

        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                raise KeyError(f"Unknown workflow run: '{run_id}'.")
            if run.status is not WorkflowStatus.WAITING_APPROVAL:
                raise ValueError(
                    f"Workflow run '{run_id}' is not waiting for approval."
                )
            if node_name not in run.approvals:
                raise KeyError(
                    f"No approval request for node '{node_name}'."
                )
            if run.approvals[node_name] is not ApprovalStatus.PENDING:
                raise ValueError(
                    f"Node '{node_name}' approval was already decided."
                )

            run.approvals[node_name] = (
                ApprovalStatus.APPROVED
                if approved
                else ApprovalStatus.REJECTED
            )
            run.approval_decisions[node_name] = approver
            if not approved:
                run.node_statuses[node_name] = NodeStatus.FAILED
                run.errors[node_name] = (
                    f"Approval rejected by '{approver}'."
                )
                run.status = WorkflowStatus.FAILED
                self._checkpoint(run)
                return run

            run.node_statuses[node_name] = NodeStatus.PENDING

        return self._resume(run_id)

    def _resume(
        self,
        run_id: str,
    ) -> WorkflowRun:
        run = self._runs[run_id]
        workflow = self._workflows[run_id]
        context = self._contexts[run_id]
        run.status = WorkflowStatus.RUNNING

        try:
            levels = self._topological_levels(workflow)
            for level in levels:
                if run.status is WorkflowStatus.CANCELLED:
                    self._checkpoint(run)
                    return run

                if all(
                    status is not NodeStatus.PENDING
                    and status is not NodeStatus.WAITING_APPROVAL
                    for name, status in run.node_statuses.items()
                    if name in {
                        node.name
                        for node in level
                    }
                ):
                    continue

                self._execute_level(
                    workflow,
                    level,
                    run,
                    context,
                )

                if any(
                    status is NodeStatus.WAITING_APPROVAL
                    for status in run.node_statuses.values()
                ):
                    run.status = WorkflowStatus.WAITING_APPROVAL
                    self._checkpoint(run)
                    return run

                if any(
                    status is NodeStatus.FAILED
                    for status in run.node_statuses.values()
                ):
                    run.status = WorkflowStatus.FAILED
                    self._checkpoint(run)
                    return run

            run.status = WorkflowStatus.COMPLETED
            self._checkpoint(run)
            return run
        except Exception as exc:
            run.status = WorkflowStatus.FAILED
            run.errors["workflow"] = str(exc)
            self._checkpoint(run)
            return run

    def cancel(
        self,
        run_id: str,
    ) -> bool:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return False
            if run.status in (
                WorkflowStatus.COMPLETED,
                WorkflowStatus.FAILED,
                WorkflowStatus.CANCELLED,
            ):
                return False

            self._cancelled.add(run_id)
            run.status = WorkflowStatus.CANCELLED
        self._checkpoint(run)
        return True

    def _execute_level(
        self,
        workflow: Workflow,
        level: list[WorkflowNode],
        run: WorkflowRun,
        context: dict,
    ) -> None:
        executor = ThreadPoolExecutor(
            max_workers=min(
                self.max_workers,
                len(level),
            )
        )
        futures: dict[Future, WorkflowNode] = {}

        try:
            with executor:
                for node in level:
                    if node.name not in run.node_statuses:
                        continue

                    dependency_failed = any(
                        run.node_statuses.get(
                            dependency,
                        ) is NodeStatus.FAILED
                        for dependency in node.dependencies
                    )
                    if dependency_failed:
                        run.node_statuses[node.name] = NodeStatus.SKIPPED
                        continue

                    if (
                        node.requires_approval
                        and node.name not in run.approvals
                    ):
                        run.approvals[node.name] = ApprovalStatus.PENDING
                        run.node_statuses[node.name] = (
                            NodeStatus.WAITING_APPROVAL
                        )
                        continue

                    if (
                        node.requires_approval
                        and run.approvals[node.name]
                        is not ApprovalStatus.APPROVED
                    ):
                        continue

                    run.node_statuses[node.name] = NodeStatus.RUNNING
                    future = executor.submit(
                        self._execute_node,
                        node,
                        context,
                        run.results,
                    )
                    futures[future] = node

                for future, node in futures.items():
                    try:
                        result = future.result(
                            timeout=node.timeout_seconds
                        )
                        with self._lock:
                            run.results[node.name] = result
                            run.node_statuses[node.name] = NodeStatus.COMPLETED
                        context[node.name] = result
                        self._checkpoint(run)
                    except FuturesTimeoutError:
                        run.errors[node.name] = (
                            f"Node timed out after "
                            f"{node.timeout_seconds} seconds."
                        )
                        run.node_statuses[node.name] = NodeStatus.FAILED
                        self._checkpoint(run)
                    except Exception as exc:
                        run.errors[node.name] = str(exc)
                        run.node_statuses[node.name] = NodeStatus.FAILED
                        self._checkpoint(run)
        finally:
            executor.shutdown(
                wait=True,
                cancel_futures=True,
            )

    def _execute_node(
        self,
        node: WorkflowNode,
        context: dict,
        results: dict[str, object],
    ) -> object:
        last_error: Exception | None = None
        attempts = node.retries + 1

        for attempt in range(attempts):
            try:
                dependency_values = {
                    dependency: results.get(dependency)
                    for dependency in node.dependencies
                }
                return node.action(
                    context,
                    dependency_values,
                )
            except Exception as exc:
                last_error = exc
                if attempt >= node.retries:
                    raise

        if last_error:
            raise last_error
        raise RuntimeError(
            f"Node '{node.name}' produced no result."
        )

    def _validate(
        self,
        workflow: Workflow,
    ) -> None:
        if not workflow.nodes:
            raise ValueError("Workflow must contain at least one node.")

        node_names = {
            node.name
            for node in workflow.nodes
        }
        if len(node_names) != len(workflow.nodes):
            raise ValueError("Workflow node names must be unique.")

        for node in workflow.nodes:
            unknown = [
                dependency
                for dependency in node.dependencies
                if dependency not in node_names
            ]
            if unknown:
                raise ValueError(
                    f"Node '{node.name}' has unknown dependencies: "
                    f"{', '.join(unknown)}"
                )

    def _topological_levels(
        self,
        workflow: Workflow,
    ) -> list[list[WorkflowNode]]:
        remaining = {
            node.name: node
            for node in workflow.nodes
        }
        completed: set[str] = set()
        levels: list[list[WorkflowNode]] = []

        while remaining:
            level = [
                node
                for node in remaining.values()
                if set(node.dependencies).issubset(completed)
            ]
            if not level:
                raise ValueError(
                    "Workflow contains a dependency cycle."
                )

            levels.append(level)
            level_names = {
                node.name
                for node in level
            }
            for name in level_names:
                del remaining[name]
            completed |= level_names

        return levels

    def _checkpoint(
        self,
        run: WorkflowRun,
    ) -> None:
        if self.checkpoint_callback:
            self.checkpoint_callback(run)
        if self.event_bus:
            self.event_bus.publish(
                run.id,
                "workflow.status",
                {
                    "run_id": run.id,
                    "workflow_id": run.workflow_id,
                    "status": run.status.value,
                    "node_statuses": {
                        name: status.value
                        for name, status in run.node_statuses.items()
                    },
                },
            )
