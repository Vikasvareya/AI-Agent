from app.workflows.engine import WorkflowEngine
from app.workflows.models import (
    ApprovalStatus,
    NodeStatus,
    Workflow,
    WorkflowNode,
    WorkflowRun,
    WorkflowStatus,
)
from app.workflows.persistence import WorkflowPersistenceStore


class APIError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
    ):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class WorkflowAPIService:
    """
    Framework-neutral REST service contract for workflows.

    HTTP adapters can translate APIError and this service's dictionaries
    into framework-specific responses without duplicating workflow logic.
    """

    def __init__(
        self,
        engine: WorkflowEngine,
        persistence_store: WorkflowPersistenceStore | None = None,
    ):
        self.engine = engine
        self._workflows: dict[str, Workflow] = {}
        self._persistence_store = persistence_store
        self._persistent_workflow_ids: set[str] = set()
        if persistence_store is not None:
            self._restore_workflows()
            self._install_checkpoint_callback()
            self._restore_runs()

    def register_workflow(
        self,
        workflow: Workflow,
    ) -> dict:
        self._workflows[workflow.id] = workflow
        return self._workflow_response(workflow)

    def list_workflows(self) -> list[dict]:
        return [
            self._workflow_response(workflow)
            for workflow in self._workflows.values()
        ]

    def create_workflow(
        self,
        definition: dict,
        *,
        persist: bool = True,
    ) -> dict:
        name = definition.get("name")
        node_definitions = definition.get("nodes")
        if not isinstance(name, str) or not name.strip():
            raise APIError(
                "INVALID_WORKFLOW",
                "Workflow name is required.",
                400,
            )
        if len(name.strip()) > 120:
            raise APIError(
                "INVALID_WORKFLOW",
                "Workflow name cannot exceed 120 characters.",
                400,
            )
        if not isinstance(node_definitions, list) or not node_definitions:
            raise APIError(
                "INVALID_WORKFLOW",
                "Workflow must contain at least one node.",
                400,
            )
        if len(node_definitions) > 50:
            raise APIError(
                "INVALID_WORKFLOW",
                "Workflow cannot contain more than 50 nodes.",
                400,
            )

        workflow = Workflow(name=name.strip())
        for node_definition in node_definitions:
            if not isinstance(node_definition, dict):
                raise APIError(
                    "INVALID_WORKFLOW",
                    "Each workflow node must be an object.",
                    400,
                )

            node_name = node_definition.get("name")
            action_kind = node_definition.get("type", "value")
            dependencies = node_definition.get("dependencies", [])
            if not isinstance(node_name, str) or not node_name.strip():
                raise APIError(
                    "INVALID_WORKFLOW",
                    "Each workflow node requires a name.",
                    400,
                )
            if len(node_name.strip()) > 80:
                raise APIError(
                    "INVALID_WORKFLOW",
                    "Workflow node names cannot exceed 80 characters.",
                    400,
                )
            if not isinstance(dependencies, list) or not all(
                isinstance(dependency, str)
                for dependency in dependencies
            ):
                raise APIError(
                    "INVALID_WORKFLOW",
                    f"Dependencies for node '{node_name}' must be strings.",
                    400,
                )
            if len(dependencies) > 50:
                raise APIError(
                    "INVALID_WORKFLOW",
                    f"Node '{node_name}' has too many dependencies.",
                    400,
                )

            if action_kind == "value":
                value = node_definition.get("value", "")
                action = lambda context, dependency_values, value=value: value
            elif action_kind == "context":
                context_key = node_definition.get("key")
                if not isinstance(context_key, str) or not context_key:
                    raise APIError(
                        "INVALID_WORKFLOW",
                        f"Context node '{node_name}' requires a key.",
                        400,
                    )
                action = lambda context, dependency_values, key=context_key: context.get(key)
            elif action_kind == "join":
                separator = node_definition.get("separator", " ")
                if not isinstance(separator, str):
                    raise APIError(
                        "INVALID_WORKFLOW",
                        f"Join separator for node '{node_name}' must be text.",
                        400,
                    )
                action = lambda context, dependency_values, separator=separator: separator.join(
                    str(value)
                    for value in dependency_values.values()
                    if value is not None
                )
            else:
                raise APIError(
                    "INVALID_WORKFLOW",
                    f"Unsupported workflow node type '{action_kind}'.",
                    400,
                )

            retries = node_definition.get("retries", 0)
            if (
                not isinstance(retries, int)
                or isinstance(retries, bool)
                or not 0 <= retries <= 5
            ):
                raise APIError(
                    "INVALID_WORKFLOW",
                    f"Retries for node '{node_name}' must be between 0 and 5.",
                    400,
                )
            requires_approval = node_definition.get(
                "requires_approval",
                False,
            )
            if not isinstance(requires_approval, bool):
                raise APIError(
                    "INVALID_WORKFLOW",
                    f"Approval setting for node '{node_name}' must be boolean.",
                    400,
                )
            timeout_seconds = node_definition.get("timeout_seconds")
            if timeout_seconds is not None and (
                isinstance(timeout_seconds, bool)
                or not isinstance(timeout_seconds, (int, float))
                or not 0 < timeout_seconds <= 300
            ):
                raise APIError(
                    "INVALID_WORKFLOW",
                    f"Timeout for node '{node_name}' must be between 0 and 300 seconds.",
                    400,
                )

            try:
                workflow.add_node(
                    WorkflowNode(
                        name=node_name.strip(),
                        action=action,
                        dependencies=dependencies,
                        retries=retries,
                        timeout_seconds=timeout_seconds,
                        requires_approval=requires_approval,
                    )
                )
            except ValueError as exc:
                raise APIError(
                    "INVALID_WORKFLOW",
                    str(exc),
                    400,
                ) from exc

        try:
            self.engine._validate(workflow)
            self.engine._topological_levels(workflow)
        except ValueError as exc:
            raise APIError(
                "INVALID_WORKFLOW",
                str(exc),
                400,
            ) from exc

        if persist and self._persistence_store is not None:
            self._persistence_store.save_workflow_definition(
                workflow.id,
                workflow.name,
                definition,
            )
            self._persistent_workflow_ids.add(workflow.id)
        self.register_workflow(workflow)
        return self._workflow_response(workflow)

    def list_runs(
        self,
        *,
        owner_id: str | None = None,
    ) -> list[dict]:
        runs = self.engine.list_runs()
        if owner_id is not None:
            runs = [
                run
                for run in runs
                if run.owner_id == owner_id
            ]
        return [
            self._run_response(run)
            for run in runs
        ]

    def create_run(
        self,
        workflow_id: str,
        *,
        idempotency_key: str | None = None,
        context: dict | None = None,
        owner_id: str | None = None,
    ) -> dict:
        workflow = self._workflows.get(workflow_id)
        if workflow is None:
            raise APIError(
                "WORKFLOW_NOT_FOUND",
                f"Workflow '{workflow_id}' was not found.",
                404,
            )

        run = self.engine.start(
            workflow,
            idempotency_key=idempotency_key,
            initial_context=context,
            owner_id=owner_id,
        )
        return self._run_response(run)

    def get_run(
        self,
        run_id: str,
    ) -> dict:
        run = self.engine.get_run(run_id)
        if run is None:
            raise APIError(
                "RUN_NOT_FOUND",
                f"Workflow run '{run_id}' was not found.",
                404,
            )
        return self._run_response(run)

    def cancel_run(
        self,
        run_id: str,
    ) -> dict:
        if not self.engine.cancel(run_id):
            run = self.engine.get_run(run_id)
            if run is None:
                raise APIError(
                    "RUN_NOT_FOUND",
                    f"Workflow run '{run_id}' was not found.",
                    404,
                )
            raise APIError(
                "RUN_NOT_CANCELLABLE",
                f"Workflow run '{run_id}' cannot be cancelled.",
                409,
            )

        return self.get_run(run_id)

    def decide_approval(
        self,
        run_id: str,
        node_name: str,
        *,
        approved: bool,
        approver: str,
    ) -> dict:
        try:
            run = self.engine.approve(
                run_id,
                node_name,
                approved=approved,
                approver=approver,
            )
        except KeyError as exc:
            raise APIError(
                "APPROVAL_TARGET_NOT_FOUND",
                str(exc).strip("'"),
                404,
            ) from exc
        except ValueError as exc:
            raise APIError(
                "INVALID_APPROVAL",
                str(exc),
                409,
            ) from exc

        return self._run_response(run)

    def _workflow_response(
        self,
        workflow: Workflow,
    ) -> dict:
        return {
            "id": workflow.id,
            "name": workflow.name,
            "nodes": [
                {
                    "name": node.name,
                    "dependencies": list(node.dependencies),
                    "retries": node.retries,
                    "timeout_seconds": node.timeout_seconds,
                    "requires_approval": node.requires_approval,
                }
                for node in workflow.nodes
            ],
        }

    def _run_response(
        self,
        run: WorkflowRun,
    ) -> dict:
        return {
            "id": run.id,
            "workflow_id": run.workflow_id,
            "status": run.status.value,
            "results": run.results,
            "node_statuses": {
                name: status.value
                for name, status in run.node_statuses.items()
            },
            "errors": run.errors,
            "idempotency_key": run.idempotency_key,
            "approvals": {
                name: status.value
                for name, status in run.approvals.items()
            },
            "approval_decisions": dict(
                run.approval_decisions
            ),
        }

    def _restore_workflows(self) -> None:
        if self._persistence_store is None:
            return
        for record in self._persistence_store.list_workflow_definitions():
            response = self.create_workflow(
                record["definition"],
                persist=False,
            )
            workflow = self._workflows.pop(response["id"])
            workflow_id = record["id"]
            if workflow.name != record["name"]:
                raise ValueError(
                    f"Persisted workflow '{workflow_id}' has inconsistent names."
                )
            workflow.id = workflow_id
            if workflow_id in self._workflows:
                raise ValueError(
                    f"Persisted workflow ID '{workflow_id}' is duplicated."
                )
            self._workflows[workflow_id] = workflow
            self._persistent_workflow_ids.add(workflow_id)

    def _install_checkpoint_callback(self) -> None:
        if self._persistence_store is None:
            return
        previous_callback = self.engine.checkpoint_callback

        def persist_checkpoint(run: WorkflowRun) -> None:
            if previous_callback is not None:
                previous_callback(run)
            if run.workflow_id in self._persistent_workflow_ids:
                self._persistence_store.save_workflow_run(
                    run.id,
                    run.workflow_id,
                    run.owner_id,
                    run.idempotency_key,
                    self._run_snapshot(run),
                )

        self.engine.checkpoint_callback = persist_checkpoint

    def _restore_runs(self) -> None:
        if self._persistence_store is None:
            return
        for record in self._persistence_store.list_workflow_runs():
            snapshot = record["snapshot"]
            run = self._run_from_snapshot(snapshot)
            if (
                run.id != record["id"]
                or run.workflow_id != record["workflow_id"]
                or run.owner_id != record["owner_id"]
                or run.idempotency_key != record["idempotency_key"]
            ):
                raise ValueError(
                    f"Persisted workflow run '{record['id']}' is inconsistent."
                )
            workflow = self._workflows.get(run.workflow_id)
            if workflow is None:
                raise ValueError(
                    f"Workflow run '{run.id}' has no persisted definition."
                )
            self.engine.restore_run(workflow, run)

    @staticmethod
    def _run_snapshot(run: WorkflowRun) -> dict:
        return {
            "version": 1,
            "id": run.id,
            "workflow_id": run.workflow_id,
            "owner_id": run.owner_id,
            "status": run.status.value,
            "results": run.results,
            "node_statuses": {
                name: status.value
                for name, status in run.node_statuses.items()
            },
            "errors": run.errors,
            "idempotency_key": run.idempotency_key,
            "approvals": {
                name: status.value
                for name, status in run.approvals.items()
            },
            "approval_decisions": run.approval_decisions,
            "initial_context": run.initial_context,
        }

    @staticmethod
    def _run_from_snapshot(snapshot: dict) -> WorkflowRun:
        if not isinstance(snapshot, dict) or snapshot.get("version") != 1:
            raise ValueError("Unsupported persisted workflow run version.")
        mapping_fields = (
            "results",
            "node_statuses",
            "errors",
            "approvals",
            "approval_decisions",
            "initial_context",
        )
        if any(
            not isinstance(snapshot.get(field), dict)
            for field in mapping_fields
        ):
            raise ValueError("Persisted workflow run maps are invalid.")
        if not isinstance(snapshot.get("id"), str) or not isinstance(
            snapshot.get("workflow_id"),
            str,
        ):
            raise ValueError("Persisted workflow run identifiers are invalid.")

        return WorkflowRun(
            id=snapshot["id"],
            workflow_id=snapshot["workflow_id"],
            status=WorkflowStatus(snapshot["status"]),
            results=snapshot["results"],
            node_statuses={
                name: NodeStatus(status)
                for name, status in snapshot["node_statuses"].items()
            },
            errors=snapshot["errors"],
            idempotency_key=snapshot.get("idempotency_key"),
            approvals={
                name: ApprovalStatus(status)
                for name, status in snapshot["approvals"].items()
            },
            approval_decisions=snapshot["approval_decisions"],
            owner_id=snapshot.get("owner_id"),
            initial_context=snapshot["initial_context"],
        )
