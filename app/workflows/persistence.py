from typing import Protocol


class WorkflowPersistenceStore(Protocol):
    def save_workflow_definition(
        self,
        workflow_id: str,
        name: str,
        definition: dict,
    ) -> None: ...

    def list_workflow_definitions(self) -> list[dict]: ...

    def save_workflow_run(
        self,
        run_id: str,
        workflow_id: str,
        owner_id: str | None,
        idempotency_key: str | None,
        snapshot: dict,
    ) -> None: ...

    def list_workflow_runs(self) -> list[dict]: ...
