from typing import Protocol


class CodingAgentPersistenceStore(Protocol):
    def list_coding_projects(self) -> list[dict]: ...

    def register_coding_project(
        self,
        project_id: str,
        name: str,
        path: str,
    ) -> dict: ...

    def get_coding_project(self, project_id: str) -> dict | None: ...

    def remove_coding_project(self, project_id: str) -> bool: ...

    def get_coding_permission_mode(self) -> str | None: ...

    def save_coding_permission_mode(
        self,
        mode: str,
        previous_mode: str,
        actor_id: str,
    ) -> None: ...

    def list_coding_proposals(self) -> list[dict]: ...

    def save_coding_proposal(
        self,
        proposal_id: str,
        owner_id: str,
        snapshot: dict,
        actor_id: str,
        details: dict,
    ) -> None: ...

    def claim_coding_proposal(
        self,
        proposal_id: str,
        owner_id: str,
        actor_id: str,
        details: dict,
    ) -> bool: ...

    def restore_coding_proposal_pending(
        self,
        proposal_id: str,
        owner_id: str,
        actor_id: str,
        details: dict,
    ) -> None: ...

    def finish_coding_proposal(
        self,
        proposal_id: str,
        owner_id: str,
        expected_status: str,
        actor_id: str,
        action: str,
        details: dict,
    ) -> bool: ...

    def list_coding_audit(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]: ...
