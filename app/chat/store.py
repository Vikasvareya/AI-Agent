from contextlib import contextmanager
import hashlib
import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4


logger = logging.getLogger(__name__)


class ChatStore:
    def __init__(
        self,
        database_path: str | Path,
        *,
        coding_audit_retention_days: int = 365,
        audit_retention_days: int = 365,
    ):
        if (
            isinstance(coding_audit_retention_days, bool)
            or not isinstance(coding_audit_retention_days, int)
            or not 0 <= coding_audit_retention_days <= 36_500
        ):
            raise ValueError(
                "Coding audit retention days must be between 0 and 36500."
            )
        if (
            isinstance(audit_retention_days, bool)
            or not isinstance(audit_retention_days, int)
            or not 0 <= audit_retention_days <= 36_500
        ):
            raise ValueError(
                "Audit retention days must be between 0 and 36500."
            )
        self.database_path = str(database_path)
        self.coding_audit_retention_days = coding_audit_retention_days
        self.audit_retention_days = audit_retention_days
        self._postgres = self.database_path.startswith(
            ("postgres://", "postgresql://")
        )
        self._postgres_url = self.database_path.replace(
            "postgres://",
            "postgresql://",
            1,
        )
        self._pool = None
        if not self._postgres and self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(
                parents=True,
                exist_ok=True,
            )
        if self._postgres:
            self._open_pool()
        self._schema_lock = Lock()
        self._initialize()

    def create_conversation(
        self,
        owner_id: str,
        title: str = "New chat",
    ) -> dict:
        now = self._now()
        conversation = {
            "id": str(uuid4()),
            "title": title,
            "created_at": now,
            "updated_at": now,
        }
        with self._connection() as connection:
            self._execute(
                connection,
                """
                INSERT INTO conversations
                    (id, owner_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    conversation["id"],
                    owner_id,
                    conversation["title"],
                    now,
                    now,
                ),
            )
        return conversation

    def list_conversations(
        self,
        owner_id: str,
        limit: int = 50,
    ) -> list[dict]:
        with self._connection() as connection:
            rows = self._execute(
                connection,
                """
                SELECT id, title, created_at, updated_at
                FROM conversations
                WHERE owner_id = ?
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """,
                (owner_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_conversation(
        self,
        owner_id: str,
        conversation_id: str,
        message_limit: int = 100,
    ) -> dict | None:
        with self._connection() as connection:
            conversation = self._execute(
                connection,
                """
                SELECT id, title, created_at, updated_at
                FROM conversations
                WHERE owner_id = ? AND id = ?
                """,
                (owner_id, conversation_id),
            ).fetchone()
            if conversation is None:
                return None
            messages = self._execute(
                connection,
                """
                SELECT id, role, content, created_at
                FROM messages
                WHERE conversation_id = ? AND status = 'complete'
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (conversation_id, message_limit),
            ).fetchall()
        return {
            **dict(conversation),
            "messages": [
                dict(message)
                for message in reversed(messages)
            ],
        }

    def begin_message(
        self,
        owner_id: str,
        conversation_id: str,
        content: str,
        client_message_id: str,
    ) -> tuple[dict | None, list[dict], bool]:
        with self._connection() as connection:
            if not self._postgres:
                self._execute(connection, "BEGIN IMMEDIATE")
            lock_clause = " FOR UPDATE" if self._postgres else ""
            conversation = self._execute(
                connection,
                """
                SELECT id, title, created_at, updated_at
                FROM conversations
                WHERE owner_id = ? AND id = ?
                """ + lock_clause,
                (owner_id, conversation_id),
            ).fetchone()
            if conversation is None:
                connection.rollback()
                return None, [], False

            existing = self._execute(
                connection,
                """
                SELECT id, content, status, created_at
                FROM messages
                WHERE conversation_id = ?
                    AND client_message_id = ?
                """,
                (conversation_id, client_message_id),
            ).fetchone()
            if existing is not None:
                if existing["content"] != content:
                    connection.rollback()
                    raise ValueError(
                        "A client message ID cannot be reused with different text."
                    )
                if existing["status"] == "pending":
                    connection.rollback()
                    raise RuntimeError(
                        "This message is already being processed."
                    )
                if existing["status"] == "complete":
                    assistant = self._execute(
                        connection,
                        """
                        SELECT id, role, content, created_at
                        FROM messages
                        WHERE reply_to = ?
                        """,
                        (existing["id"],),
                    ).fetchone()
                    connection.rollback()
                    if assistant is not None:
                        return (
                            {
                                "id": existing["id"],
                                "role": "user",
                                "content": existing["content"],
                                "created_at": existing["created_at"],
                            },
                            [dict(assistant)],
                            True,
                        )
                self._execute(
                    connection,
                    """
                    UPDATE messages
                    SET status = 'pending'
                    WHERE id = ?
                    """,
                    (existing["id"],),
                )
                user_message_id = existing["id"]
                user_created_at = existing["created_at"]
            else:
                user_message_id = str(uuid4())
                user_created_at = self._now()
                self._execute(
                    connection,
                    """
                    INSERT INTO messages
                        (id, conversation_id, role, content, created_at,
                         status, client_message_id)
                    VALUES (?, ?, 'user', ?, ?, 'pending', ?)
                    """,
                    (
                        user_message_id,
                        conversation_id,
                        content,
                        user_created_at,
                        client_message_id,
                    ),
                )

            now = self._now()
            if conversation["title"] == "New chat":
                title = content[:72].strip() or "New chat"
            else:
                title = conversation["title"]
            self._execute(
                connection,
                """
                UPDATE conversations
                SET title = ?, updated_at = ?
                WHERE id = ?
                """,
                (title, now, conversation_id),
            )
            history = self._execute(
                connection,
                """
                SELECT role, content
                FROM messages
                WHERE conversation_id = ?
                    AND (
                        status = 'complete'
                        OR id = ?
                    )
                ORDER BY created_at DESC, id DESC
                LIMIT 20
                """,
                (conversation_id, user_message_id),
            ).fetchall()
            connection.commit()

        user_message = {
            "id": user_message_id,
            "role": "user",
            "content": content,
            "created_at": user_created_at,
        }
        return user_message, [
            dict(message)
            for message in reversed(history)
        ], False

    def complete_message(
        self,
        conversation_id: str,
        user_message_id: str,
        content: str,
    ) -> dict:
        now = self._now()
        assistant = {
            "id": str(uuid4()),
            "role": "assistant",
            "content": content,
            "created_at": now,
        }
        with self._connection() as connection:
            if not self._postgres:
                self._execute(connection, "BEGIN IMMEDIATE")
            self._execute(
                connection,
                """
                INSERT INTO messages
                    (id, conversation_id, role, content, created_at,
                     status, reply_to)
                VALUES (?, ?, 'assistant', ?, ?, 'complete', ?)
                """,
                (
                    assistant["id"],
                    conversation_id,
                    content,
                    now,
                    user_message_id,
                ),
            )
            self._execute(
                connection,
                """
                UPDATE messages
                SET status = 'complete'
                WHERE id = ? AND conversation_id = ?
                """,
                (user_message_id, conversation_id),
            )
            self._execute(
                connection,
                """
                UPDATE conversations
                SET updated_at = ?
                WHERE id = ?
                """,
                (now, conversation_id),
            )
            connection.commit()
        return assistant

    def fail_message(
        self,
        conversation_id: str,
        user_message_id: str,
    ) -> None:
        with self._connection() as connection:
            self._execute(
                connection,
                """
                UPDATE messages
                SET status = 'failed'
                WHERE id = ? AND conversation_id = ?
                """,
                (user_message_id, conversation_id),
            )

    def delete_conversation(
        self,
        owner_id: str,
        conversation_id: str,
    ) -> bool:
        with self._connection() as connection:
            cursor = self._execute(
                connection,
                """
                DELETE FROM conversations
                WHERE owner_id = ? AND id = ?
                """,
                (owner_id, conversation_id),
            )
            return cursor.rowcount > 0

    def list_coding_projects(self) -> list[dict]:
        with self._connection() as connection:
            rows = self._execute(
                connection,
                """
                SELECT id, name, path, created_at
                FROM coding_projects
                ORDER BY LOWER(name), id
                """,
            ).fetchall()
        return [dict(row) for row in rows]

    def register_coding_project(
        self,
        project_id: str,
        name: str,
        path: str,
    ) -> dict:
        path_key = os.path.normcase(os.path.normpath(path))
        now = self._now()
        with self._connection() as connection:
            self._execute(
                connection,
                """
                INSERT INTO coding_projects (id, name, path, path_key, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(path_key) DO NOTHING
                """,
                (project_id, name, path, path_key, now),
            )
            row = self._execute(
                connection,
                """
                SELECT id, name, path, created_at
                FROM coding_projects
                WHERE path_key = ?
                """,
                (path_key,),
            ).fetchone()
        if row is None:
            raise RuntimeError("The coding project could not be registered.")
        return dict(row)

    def get_coding_project(self, project_id: str) -> dict | None:
        with self._connection() as connection:
            row = self._execute(
                connection,
                """
                SELECT id, name, path, created_at
                FROM coding_projects
                WHERE id = ?
                """,
                (project_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def remove_coding_project(self, project_id: str) -> bool:
        with self._connection() as connection:
            cursor = self._execute(
                connection,
                "DELETE FROM coding_projects WHERE id = ?",
                (project_id,),
            )
        return cursor.rowcount > 0

    def create_coding_session(
        self,
        owner_id: str,
        project_id: str,
        title: str,
    ) -> dict:
        now = self._now()
        session = {
            "id": str(uuid4()),
            "project_id": project_id,
            "title": title,
            "created_at": now,
            "updated_at": now,
        }
        with self._connection() as connection:
            self._execute(
                connection,
                """
                INSERT INTO coding_sessions
                    (id, owner_id, project_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session["id"],
                    owner_id,
                    project_id,
                    title,
                    now,
                    now,
                ),
            )
        return session

    def list_coding_sessions(
        self,
        owner_id: str,
        project_id: str,
        limit: int = 50,
    ) -> list[dict]:
        with self._connection() as connection:
            rows = self._execute(
                connection,
                """
                SELECT id, project_id, title, created_at, updated_at
                FROM coding_sessions
                WHERE owner_id = ? AND project_id = ?
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """,
                (owner_id, project_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_coding_session(
        self,
        owner_id: str,
        session_id: str,
        message_limit: int = 100,
    ) -> dict | None:
        with self._connection() as connection:
            session = self._execute(
                connection,
                """
                SELECT id, project_id, title, created_at, updated_at
                FROM coding_sessions
                WHERE owner_id = ? AND id = ?
                """,
                (owner_id, session_id),
            ).fetchone()
            if session is None:
                return None
            messages = self._execute(
                connection,
                """
                SELECT id, role, content, created_at
                FROM coding_session_messages
                WHERE session_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (session_id, message_limit),
            ).fetchall()
        return {
            **dict(session),
            "messages": [
                dict(message)
                for message in reversed(messages)
            ],
        }

    def delete_coding_session(
        self,
        owner_id: str,
        session_id: str,
        actor_id: str,
    ) -> bool:
        with self._connection() as connection:
            session = self._execute(
                connection,
                """
                SELECT project_id
                FROM coding_sessions
                WHERE owner_id = ? AND id = ?
                """,
                (owner_id, session_id),
            ).fetchone()
            if session is None:
                return False
            now = self._now()
            self._delete_pending_coding_proposals(
                connection,
                actor_id,
                session_ids={session_id},
                owner_id=owner_id,
            )
            cursor = self._execute(
                connection,
                """
                DELETE FROM coding_sessions
                WHERE owner_id = ? AND id = ?
                """,
                (owner_id, session_id),
            )
            if cursor.rowcount:
                self._insert_coding_audit(
                    connection,
                    actor_id,
                    "coding_session_deleted",
                    session_id,
                    {"project_id": session["project_id"]},
                    now,
                )
            return cursor.rowcount > 0

    def delete_coding_sessions_for_project(
        self,
        project_id: str,
        actor_id: str,
    ) -> int:
        with self._connection() as connection:
            sessions = self._execute(
                connection,
                "SELECT id FROM coding_sessions WHERE project_id = ?",
                (project_id,),
            ).fetchall()
            session_ids = {row["id"] for row in sessions}
            now = self._now()
            self._delete_pending_coding_proposals(
                connection,
                actor_id,
                session_ids=session_ids,
                project_id=project_id,
            )
            cursor = self._execute(
                connection,
                "DELETE FROM coding_sessions WHERE project_id = ?",
                (project_id,),
            )
            self._insert_coding_audit(
                connection,
                actor_id,
                "coding_project_deleted",
                project_id,
                {"deleted_conversations": cursor.rowcount},
                now,
            )
            return cursor.rowcount

    def _delete_pending_coding_proposals(
        self,
        connection,
        actor_id: str,
        *,
        session_ids: set[str],
        owner_id: str | None = None,
        project_id: str | None = None,
    ) -> int:
        rows = self._execute(
            connection,
            """
            SELECT id, owner_id, snapshot
            FROM coding_proposals
            WHERE status = 'pending'
            """,
        ).fetchall()
        deleted = 0
        now = self._now()
        for row in rows:
            if owner_id is not None and row["owner_id"] != owner_id:
                continue
            snapshot = json.loads(row["snapshot"])
            if (
                snapshot.get("session_id") not in session_ids
                and (
                    project_id is None
                    or snapshot.get("project_id") != project_id
                )
            ):
                continue
            cursor = self._execute(
                connection,
                """
                DELETE FROM coding_proposals
                WHERE id = ? AND owner_id = ? AND status = 'pending'
                """,
                (row["id"], row["owner_id"]),
            )
            if cursor.rowcount:
                deleted += 1
                self._insert_coding_audit(
                    connection,
                    actor_id,
                    "coding_proposal_discarded",
                    row["id"],
                    {"reason": "conversation_deleted"},
                    now,
                )
        return deleted

    def append_coding_session_message(
        self,
        owner_id: str,
        session_id: str,
        role: str,
        content: str,
    ) -> dict | None:
        if role not in ("user", "assistant"):
            raise ValueError("Coding session message role is invalid.")
        if not isinstance(content, str) or len(content) > 100_000:
            raise ValueError("Coding session messages cannot exceed 100,000 characters.")
        now = self._now()
        message = {
            "id": str(uuid4()),
            "role": role,
            "content": content,
            "created_at": now,
        }
        with self._connection() as connection:
            session = self._execute(
                connection,
                "SELECT id FROM coding_sessions WHERE owner_id = ? AND id = ?",
                (owner_id, session_id),
            ).fetchone()
            if session is None:
                return None
            self._execute(
                connection,
                """
                INSERT INTO coding_session_messages
                    (id, session_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (message["id"], session_id, role, content, now),
            )
            self._execute(
                connection,
                """
                UPDATE coding_sessions
                SET title = CASE
                        WHEN title = 'New session' AND ? = 'user'
                        THEN substr(?, 1, 72)
                        ELSE title
                    END,
                    updated_at = ?
                WHERE id = ?
                """,
                (role, content, now, session_id),
            )
            self._execute(
                connection,
                """
                DELETE FROM coding_session_messages
                WHERE session_id = ? AND id NOT IN (
                    SELECT id
                    FROM coding_session_messages
                    WHERE session_id = ?
                    ORDER BY created_at DESC, id DESC
                    LIMIT 100
                )
                """,
                (session_id, session_id),
            )
        return message

    def create_coding_session_share(
        self,
        owner_id: str,
        session_id: str,
        token: str,
        expires_at: str,
    ) -> bool:
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self._connection() as connection:
            session = self._execute(
                connection,
                "SELECT id FROM coding_sessions WHERE owner_id = ? AND id = ?",
                (owner_id, session_id),
            ).fetchone()
            if session is None:
                return False
            self._execute(
                connection,
                """
                INSERT INTO coding_session_shares
                    (token_hash, owner_id, session_id, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (token_hash, owner_id, session_id, self._now(), expires_at),
            )
        return True

    def revoke_coding_session_share(
        self,
        owner_id: str,
        session_id: str,
        token: str,
    ) -> bool:
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self._connection() as connection:
            cursor = self._execute(
                connection,
                """
                DELETE FROM coding_session_shares
                WHERE token_hash = ? AND owner_id = ? AND session_id = ?
                """,
                (token_hash, owner_id, session_id),
            )
            return cursor.rowcount > 0

    def revoke_coding_session_shares(
        self,
        owner_id: str,
        session_id: str,
    ) -> int:
        with self._connection() as connection:
            cursor = self._execute(
                connection,
                """
                DELETE FROM coding_session_shares
                WHERE owner_id = ? AND session_id = ?
                """,
                (owner_id, session_id),
            )
            return cursor.rowcount

    def get_shared_coding_session(self, token: str) -> dict | None:
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now = self._now()
        with self._connection() as connection:
            share = self._execute(
                connection,
                """
                SELECT session_id, owner_id
                FROM coding_session_shares
                WHERE token_hash = ? AND expires_at > ?
                """,
                (token_hash, now),
            ).fetchone()
            if share is None:
                return None
        return self.get_coding_session(share["owner_id"], share["session_id"])

    def get_coding_permission_mode(self) -> str | None:
        with self._connection() as connection:
            row = self._execute(
                connection,
                """
                SELECT mode
                FROM coding_agent_settings
                WHERE id = 'global'
                """,
            ).fetchone()
        return row["mode"] if row is not None else None

    def save_coding_permission_mode(
        self,
        mode: str,
        previous_mode: str,
        actor_id: str,
    ) -> None:
        now = self._now()
        details = {
            "previous_mode": previous_mode,
            "mode": mode,
        }
        with self._connection() as connection:
            self._execute(
                connection,
                """
                INSERT INTO coding_agent_settings (id, mode, updated_at)
                VALUES ('global', ?, ?)
                ON CONFLICT (id) DO UPDATE SET
                    mode = excluded.mode,
                    updated_at = excluded.updated_at
                """,
                (mode, now),
            )
            self._insert_coding_audit(
                connection,
                actor_id,
                "permission_mode_set",
                None,
                details,
                now,
            )

    def list_coding_proposals(self) -> list[dict]:
        with self._connection() as connection:
            rows = self._execute(
                connection,
                """
                SELECT id, owner_id, status, snapshot, created_at, updated_at
                FROM coding_proposals
                WHERE status IN ('pending', 'applying')
                ORDER BY created_at, id
                """,
            ).fetchall()
        return [
            {
                **dict(row),
                "snapshot": json.loads(row["snapshot"]),
            }
            for row in rows
        ]

    def save_coding_proposal(
        self,
        proposal_id: str,
        owner_id: str,
        snapshot: dict,
        actor_id: str,
        details: dict,
    ) -> None:
        serialized = json.dumps(
            snapshot,
            separators=(",", ":"),
            sort_keys=True,
        )
        now = self._now()
        with self._connection() as connection:
            self._execute(
                connection,
                """
                INSERT INTO coding_proposals
                    (id, owner_id, status, snapshot, created_at, updated_at)
                VALUES (?, ?, 'pending', ?, ?, ?)
                """,
                (proposal_id, owner_id, serialized, now, now),
            )
            self._insert_coding_audit(
                connection,
                actor_id,
                "proposal_created",
                proposal_id,
                details,
                now,
            )

    def claim_coding_proposal(
        self,
        proposal_id: str,
        owner_id: str,
        actor_id: str,
        details: dict,
    ) -> bool:
        now = self._now()
        with self._connection() as connection:
            cursor = self._execute(
                connection,
                """
                UPDATE coding_proposals
                SET status = 'applying', updated_at = ?
                WHERE id = ? AND owner_id = ? AND status = 'pending'
                """,
                (now, proposal_id, owner_id),
            )
            if cursor.rowcount == 0:
                return False
            self._insert_coding_audit(
                connection,
                actor_id,
                "proposal_apply_started",
                proposal_id,
                details,
                now,
            )
            return True

    def restore_coding_proposal_pending(
        self,
        proposal_id: str,
        owner_id: str,
        actor_id: str,
        details: dict,
    ) -> None:
        now = self._now()
        with self._connection() as connection:
            cursor = self._execute(
                connection,
                """
                UPDATE coding_proposals
                SET status = 'pending', updated_at = ?
                WHERE id = ? AND owner_id = ? AND status = 'applying'
                """,
                (now, proposal_id, owner_id),
            )
            if cursor.rowcount:
                self._insert_coding_audit(
                    connection,
                    actor_id,
                    "proposal_apply_failed",
                    proposal_id,
                    details,
                    now,
                )

    def finish_coding_proposal(
        self,
        proposal_id: str,
        owner_id: str,
        expected_status: str,
        actor_id: str,
        action: str,
        details: dict,
    ) -> bool:
        if expected_status not in ("pending", "applying"):
            raise ValueError("Invalid expected coding proposal status.")
        now = self._now()
        with self._connection() as connection:
            cursor = self._execute(
                connection,
                """
                DELETE FROM coding_proposals
                WHERE id = ? AND owner_id = ? AND status = ?
                """,
                (proposal_id, owner_id, expected_status),
            )
            if cursor.rowcount == 0:
                return False
            self._insert_coding_audit(
                connection,
                actor_id,
                action,
                proposal_id,
                details,
                now,
            )
            return True

    def list_coding_audit(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        with self._connection() as connection:
            self._prune_coding_audit(connection)
            rows = self._execute(
                connection,
                """
                SELECT id, actor_id, action, resource_id, details, created_at
                FROM coding_audit
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return [
            {
                **dict(row),
                "details": json.loads(row["details"]),
            }
            for row in rows
        ]

    def prune_coding_audit(self) -> int:
        with self._connection() as connection:
            return self._prune_coding_audit(connection)

    def record_audit(
        self,
        actor_id: str,
        action: str,
        resource_id: str | None = None,
        details: dict | None = None,
    ) -> dict:
        now = self._now()
        event = {
            "id": str(uuid4()),
            "actor_id": actor_id,
            "action": action,
            "resource_id": resource_id,
            "details": details or {},
            "created_at": now,
        }
        with self._connection() as connection:
            self._prune_audit(connection)
            self._execute(
                connection,
                """
                INSERT INTO audit_events
                    (id, actor_id, action, resource_id, details, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event["id"],
                    event["actor_id"],
                    event["action"],
                    event["resource_id"],
                    json.dumps(
                        event["details"],
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                    event["created_at"],
                ),
            )
        return event

    def list_audit(
        self,
        limit: int = 50,
        offset: int = 0,
        action: str | None = None,
    ) -> list[dict]:
        with self._connection() as connection:
            self._prune_audit(connection)
            if action:
                rows = self._execute(
                    connection,
                    """
                    SELECT id, actor_id, action, resource_id, details, created_at
                    FROM audit_events
                    WHERE action = ?
                    ORDER BY created_at DESC, id DESC
                    LIMIT ? OFFSET ?
                    """,
                    (action, limit, offset),
                ).fetchall()
            else:
                rows = self._execute(
                    connection,
                    """
                    SELECT id, actor_id, action, resource_id, details, created_at
                    FROM audit_events
                    ORDER BY created_at DESC, id DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                ).fetchall()
        return [
            {
                **dict(row),
                "details": json.loads(row["details"]),
            }
            for row in rows
        ]

    def prune_audit(self) -> int:
        with self._connection() as connection:
            return self._prune_audit(connection)

    def _prune_audit(self, connection) -> int:
        if self.audit_retention_days == 0:
            return 0
        cutoff = (
            datetime.now(timezone.utc)
            - timedelta(days=self.audit_retention_days)
        ).isoformat()
        cursor = self._execute(
            connection,
            "DELETE FROM audit_events WHERE created_at < ?",
            (cutoff,),
        )
        if cursor.rowcount:
            logger.info(
                "Pruned %s expired audit events.",
                cursor.rowcount,
            )
        return cursor.rowcount

    def _prune_coding_audit(self, connection) -> int:
        if self.coding_audit_retention_days == 0:
            return 0
        cutoff = (
            datetime.now(timezone.utc)
            - timedelta(days=self.coding_audit_retention_days)
        ).isoformat()
        cursor = self._execute(
            connection,
            "DELETE FROM coding_audit WHERE created_at < ?",
            (cutoff,),
        )
        if cursor.rowcount:
            logger.info(
                "Pruned %s expired coding audit events.",
                cursor.rowcount,
            )
        return cursor.rowcount

    def _insert_coding_audit(
        self,
        connection,
        actor_id: str,
        action: str,
        resource_id: str | None,
        details: dict,
        created_at: str,
    ) -> None:
        self._prune_coding_audit(connection)
        self._prune_audit(connection)
        event_id = str(uuid4())
        self._execute(
            connection,
            """
            INSERT INTO coding_audit
                (id, actor_id, action, resource_id, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                actor_id,
                action,
                resource_id,
                json.dumps(
                    details,
                    separators=(",", ":"),
                    sort_keys=True,
                ),
                created_at,
            ),
        )
        self._execute(
            connection,
            """
            INSERT INTO audit_events
                (id, actor_id, action, resource_id, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                actor_id,
                action,
                resource_id,
                json.dumps(
                    details,
                    separators=(",", ":"),
                    sort_keys=True,
                ),
                created_at,
            ),
        )

    def save_workflow_definition(
        self,
        workflow_id: str,
        name: str,
        definition: dict,
    ) -> None:
        serialized = json.dumps(
            definition,
            separators=(",", ":"),
            sort_keys=True,
        )
        now = self._now()
        with self._connection() as connection:
            self._execute(
                connection,
                """
                INSERT INTO workflow_definitions
                    (id, name, definition, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (id) DO UPDATE SET
                    name = excluded.name,
                    definition = excluded.definition,
                    updated_at = excluded.updated_at
                """,
                (workflow_id, name, serialized, now, now),
            )

    def list_workflow_definitions(self) -> list[dict]:
        with self._connection() as connection:
            rows = self._execute(
                connection,
                """
                SELECT id, name, definition, created_at, updated_at
                FROM workflow_definitions
                ORDER BY created_at, id
                """,
            ).fetchall()
        return [
            {
                **dict(row),
                "definition": json.loads(row["definition"]),
            }
            for row in rows
        ]

    def save_workflow_run(
        self,
        run_id: str,
        workflow_id: str,
        owner_id: str | None,
        idempotency_key: str | None,
        snapshot: dict,
    ) -> None:
        if (
            snapshot.get("id") != run_id
            or snapshot.get("workflow_id") != workflow_id
        ):
            raise ValueError("Workflow run snapshot identifiers do not match.")
        serialized = json.dumps(
            snapshot,
            separators=(",", ":"),
            sort_keys=True,
        )
        now = self._now()
        with self._connection() as connection:
            self._execute(
                connection,
                """
                INSERT INTO workflow_runs
                    (id, workflow_id, owner_id, idempotency_key,
                     snapshot, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (id) DO UPDATE SET
                    workflow_id = excluded.workflow_id,
                    owner_id = excluded.owner_id,
                    idempotency_key = excluded.idempotency_key,
                    snapshot = excluded.snapshot,
                    updated_at = excluded.updated_at
                """,
                (
                    run_id,
                    workflow_id,
                    owner_id,
                    idempotency_key,
                    serialized,
                    now,
                    now,
                ),
            )

    def list_workflow_runs(self) -> list[dict]:
        with self._connection() as connection:
            rows = self._execute(
                connection,
                """
                SELECT id, workflow_id, owner_id, idempotency_key,
                       snapshot, created_at, updated_at
                FROM workflow_runs
                ORDER BY created_at, id
                """,
            ).fetchall()
        return [
            {
                **dict(row),
                "snapshot": json.loads(row["snapshot"]),
            }
            for row in rows
        ]

    def create_api_credential(
        self,
        credential_id: str,
        token_hash: str,
        role: str,
        subject: str,
        expires_at: str,
    ) -> dict:
        now = self._now()
        with self._connection() as connection:
            self._execute(
                connection,
                """
                INSERT INTO api_credentials
                    (id, token_hash, role, subject, expires_at,
                     revoked_at, created_at)
                VALUES (?, ?, ?, ?, ?, NULL, ?)
                """,
                (
                    credential_id,
                    token_hash,
                    role,
                    subject,
                    expires_at,
                    now,
                ),
            )
        return {
            "id": credential_id,
            "role": role,
            "subject": subject,
            "expires_at": expires_at,
            "created_at": now,
        }

    def authenticate_api_credential(
        self,
        token_hash: str,
    ) -> tuple[str, str] | None:
        now = self._now()
        with self._connection() as connection:
            row = self._execute(
                connection,
                """
                SELECT role, subject
                FROM api_credentials
                WHERE token_hash = ?
                  AND revoked_at IS NULL
                  AND expires_at > ?
                """,
                (token_hash, now),
            ).fetchone()
        if row is None:
            return None
        return (row["role"], row["subject"])

    def allow_distributed_request(
        self,
        client_id: str,
        max_requests: int,
        window_seconds: int,
    ) -> bool:
        if max_requests <= 0 or window_seconds <= 0:
            raise ValueError("Rate limit values must be greater than zero.")
        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(seconds=window_seconds)).isoformat()
        now_text = now.isoformat()
        with self._connection() as connection:
            if not self._postgres:
                self._execute(connection, "BEGIN IMMEDIATE")
            self._execute(
                connection,
                "DELETE FROM api_rate_limit_hits WHERE client_id = ? AND occurred_at < ?",
                (client_id, cutoff),
            )
            row = self._execute(
                connection,
                """
                SELECT COUNT(*) AS request_count
                FROM api_rate_limit_hits
                WHERE client_id = ?
                """,
                (client_id,),
            ).fetchone()
            request_count = int(row["request_count"])
            if request_count >= max_requests:
                if not self._postgres:
                    connection.commit()
                return False
            self._execute(
                connection,
                """
                INSERT INTO api_rate_limit_hits
                    (id, client_id, occurred_at)
                VALUES (?, ?, ?)
                """,
                (str(uuid4()), client_id, now_text),
            )
        return True

    def revoke_api_credential(self, credential_id: str) -> bool:
        now = self._now()
        with self._connection() as connection:
            cursor = self._execute(
                connection,
                """
                UPDATE api_credentials
                SET revoked_at = ?
                WHERE id = ? AND revoked_at IS NULL
                """,
                (now, credential_id),
            )
        return cursor.rowcount == 1

    def get_api_credential(self, credential_id: str) -> dict | None:
        with self._connection() as connection:
            row = self._execute(
                connection,
                """
                SELECT id, role, subject, expires_at, revoked_at, created_at
                FROM api_credentials
                WHERE id = ?
                """,
                (credential_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def list_api_credentials(self) -> list[dict]:
        with self._connection() as connection:
            rows = self._execute(
                connection,
                """
                SELECT id, role, subject, expires_at, revoked_at, created_at
                FROM api_credentials
                ORDER BY created_at DESC, id DESC
                """,
            ).fetchall()
        return [dict(row) for row in rows]

    def prune_api_credentials(
        self,
        retention_days: int = 30,
    ) -> int:
        if (
            isinstance(retention_days, bool)
            or not isinstance(retention_days, int)
            or retention_days < 0
            or retention_days > 36_500
        ):
            raise ValueError(
                "API credential retention days must be between 0 and 36500."
            )
        if retention_days == 0:
            cutoff = datetime.now(timezone.utc).isoformat()
        else:
            cutoff = (
                datetime.now(timezone.utc)
                - timedelta(days=retention_days)
            ).isoformat()
        with self._connection() as connection:
            cursor = self._execute(
                connection,
                """
                DELETE FROM api_credentials
                WHERE (revoked_at IS NOT NULL AND revoked_at < ?)
                   OR expires_at < ?
                """,
                (cutoff, cutoff),
            )
        if cursor.rowcount:
            logger.info(
                "Pruned %s expired or revoked API credentials.",
                cursor.rowcount,
            )
        return cursor.rowcount

    def prune_api_rate_limit_hits(
        self,
        retention_seconds: int = 86_400,
    ) -> int:
        if (
            isinstance(retention_seconds, bool)
            or not isinstance(retention_seconds, int)
            or retention_seconds < 0
        ):
            raise ValueError(
                "API rate-limit retention seconds must be non-negative."
            )
        cutoff = (
            datetime.now(timezone.utc)
            - timedelta(seconds=retention_seconds)
        ).isoformat()
        with self._connection() as connection:
            cursor = self._execute(
                connection,
                "DELETE FROM api_rate_limit_hits WHERE occurred_at < ?",
                (cutoff,),
            )
        if cursor.rowcount:
            logger.info(
                "Pruned %s expired API rate-limit hits.",
                cursor.rowcount,
            )
        return cursor.rowcount

    def _open_pool(self) -> None:
        try:
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool
        except ImportError as exc:
            raise RuntimeError(
                "PostgreSQL chat storage requires psycopg; install "
                "the optional chat requirements."
            ) from exc
        self._pool = ConnectionPool(
            self._postgres_url,
            min_size=1,
            max_size=20,
            timeout=10,
            kwargs={
                "connect_timeout": 10,
                "row_factory": dict_row,
            },
            open=False,
        )
        self._pool.open(wait=True, timeout=10)

    @contextmanager
    def _connection(self):
        if self._postgres:
            with self._pool.connection() as connection:
                yield connection
            return
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close()

    def health_check(self) -> bool:
        if self._postgres:
            from psycopg import Error as PostgresError
            from psycopg_pool import PoolTimeout

            try:
                with self._pool.connection(timeout=2) as connection:
                    self._execute(connection, "SELECT 1").fetchone()
            except (PostgresError, PoolTimeout):
                return False
            return True

        try:
            with self._connection() as connection:
                self._execute(connection, "SELECT 1").fetchone()
        except sqlite3.Error:
            return False
        return True

    def _execute(
        self,
        connection,
        statement: str,
        parameters: tuple = (),
    ):
        if self._postgres:
            statement = statement.replace("?", "%s")
        return connection.execute(statement, parameters)

    def _initialize(self) -> None:
        with self._schema_lock:
            with self._connection() as connection:
                if not self._postgres and self.database_path != ":memory:":
                    self._execute(connection, "PRAGMA journal_mode = WAL")
                statements = (
                    """
                    CREATE TABLE IF NOT EXISTS conversations (
                        id TEXT PRIMARY KEY,
                        owner_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """,
                    """
                    CREATE INDEX IF NOT EXISTS
                        idx_conversations_owner_updated
                    ON conversations (owner_id, updated_at DESC);
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS messages (
                        id TEXT PRIMARY KEY,
                        conversation_id TEXT NOT NULL
                            REFERENCES conversations(id) ON DELETE CASCADE,
                        role TEXT NOT NULL
                            CHECK (role IN ('user', 'assistant')),
                        content TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        status TEXT NOT NULL
                            CHECK (status IN ('pending', 'complete', 'failed')),
                        client_message_id TEXT,
                        reply_to TEXT UNIQUE REFERENCES messages(id),
                        UNIQUE (conversation_id, client_message_id)
                    )
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS coding_sessions (
                        id TEXT PRIMARY KEY,
                        owner_id TEXT NOT NULL,
                        project_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """,
                    """
                    CREATE INDEX IF NOT EXISTS
                        idx_coding_sessions_owner_project_updated
                    ON coding_sessions (owner_id, project_id, updated_at DESC)
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS coding_projects (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        path TEXT NOT NULL,
                        path_key TEXT NOT NULL UNIQUE,
                        created_at TEXT NOT NULL
                    )
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS coding_session_messages (
                        id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL
                            REFERENCES coding_sessions(id) ON DELETE CASCADE,
                        role TEXT NOT NULL
                            CHECK (role IN ('user', 'assistant')),
                        content TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """,
                    """
                    CREATE INDEX IF NOT EXISTS
                        idx_coding_session_messages_session_created
                    ON coding_session_messages (session_id, created_at, id)
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS coding_session_shares (
                        token_hash TEXT PRIMARY KEY,
                        owner_id TEXT NOT NULL,
                        session_id TEXT NOT NULL
                            REFERENCES coding_sessions(id) ON DELETE CASCADE,
                        created_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL
                    )
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS workflow_definitions (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        definition TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS workflow_runs (
                        id TEXT PRIMARY KEY,
                        workflow_id TEXT NOT NULL
                            REFERENCES workflow_definitions(id),
                        owner_id TEXT,
                        idempotency_key TEXT,
                        snapshot TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS api_credentials (
                        id TEXT PRIMARY KEY,
                        token_hash TEXT NOT NULL UNIQUE,
                        role TEXT NOT NULL
                            CHECK (role IN ('admin', 'user')),
                        subject TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        revoked_at TEXT,
                        created_at TEXT NOT NULL
                    )
                    """,
                    """
                    CREATE INDEX IF NOT EXISTS
                        idx_api_credentials_token_expiry
                    ON api_credentials (token_hash, expires_at, revoked_at)
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS api_rate_limit_hits (
                        id TEXT PRIMARY KEY,
                        client_id TEXT NOT NULL,
                        occurred_at TEXT NOT NULL
                    )
                    """,
                    """
                    CREATE INDEX IF NOT EXISTS
                        idx_api_rate_limit_client_time
                    ON api_rate_limit_hits (client_id, occurred_at)
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS coding_agent_settings (
                        id TEXT PRIMARY KEY,
                        mode TEXT NOT NULL
                            CHECK (mode IN ('manual', 'auto')),
                        updated_at TEXT NOT NULL
                    )
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS coding_proposals (
                        id TEXT PRIMARY KEY,
                        owner_id TEXT NOT NULL,
                        status TEXT NOT NULL
                            CHECK (status IN ('pending', 'applying')),
                        snapshot TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """,
                    """
                    CREATE INDEX IF NOT EXISTS
                        idx_coding_proposals_owner_status_created
                    ON coding_proposals (owner_id, status, created_at)
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS coding_audit (
                        id TEXT PRIMARY KEY,
                        actor_id TEXT NOT NULL,
                        action TEXT NOT NULL,
                        resource_id TEXT,
                        details TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """,
                    """
                    CREATE INDEX IF NOT EXISTS
                        idx_coding_audit_created_id
                    ON coding_audit (created_at DESC, id DESC)
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS audit_events (
                        id TEXT PRIMARY KEY,
                        actor_id TEXT NOT NULL,
                        action TEXT NOT NULL,
                        resource_id TEXT,
                        details TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """,
                    """
                    CREATE INDEX IF NOT EXISTS
                        idx_audit_events_created_id
                    ON audit_events (created_at DESC, id DESC)
                    """,
                    """
                    CREATE INDEX IF NOT EXISTS
                        idx_workflow_runs_owner_updated
                    ON workflow_runs (owner_id, updated_at DESC)
                    """,
                    """
                    CREATE INDEX IF NOT EXISTS
                        idx_messages_conversation_created
                    ON messages (conversation_id, created_at, id)
                    """,
                )
                for statement in statements:
                    self._execute(connection, statement)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
