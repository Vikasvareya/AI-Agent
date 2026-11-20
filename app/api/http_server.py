import json
import os
import time
import hashlib
import hmac
import mimetypes
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock, Thread
from urllib.parse import parse_qs, unquote, urlparse

from app.agents.coding_agent import CodingAgent, CodingAgentError
from app.api.security_config import validate_api_auth
from app.api.workflow_service import APIError, WorkflowAPIService
from app.chat.service import ChatError, ChatService
from app.realtime.event_bus import EventBus
from app.realtime.models import WorkflowEvent
from app.workflows.engine import WorkflowEngine
from app.workflows.models import Workflow, WorkflowNode


class APIRateLimiter:
    def __init__(
        self,
        max_requests: int = 120,
        window_seconds: int = 60,
    ):
        if max_requests <= 0 or window_seconds <= 0:
            raise ValueError(
                "Rate limit values must be greater than zero."
            )
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = {}
        self._lock = Lock()

    def allow(
        self,
        client_id: str,
    ) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            timestamps = [
                timestamp
                for timestamp in self._requests.get(
                    client_id,
                    [],
                )
                if timestamp > cutoff
            ]
            if len(timestamps) >= self.max_requests:
                self._requests[client_id] = timestamps
                return False

            timestamps.append(now)
            self._requests[client_id] = timestamps
            return True


class WorkflowHTTPServer:
    def __init__(
        self,
        api: WorkflowAPIService,
        event_bus: EventBus,
        *,
        host: str = "127.0.0.1",
        port: int = 8081,
        api_token: str | None = None,
        role_tokens: dict[str, str | tuple[str, str]] | None = None,
        require_auth: bool = False,
        rate_limiter: APIRateLimiter | None = None,
        chat_service: ChatService | None = None,
        coding_agent: CodingAgent | None = None,
        secure_guest_cookies: bool = False,
    ):
        self.api = api
        self.event_bus = event_bus
        self.host = host
        self.port = port
        self.api_token = api_token
        self.role_tokens = role_tokens or {}
        self.require_auth = require_auth
        has_configured_token = bool(api_token and api_token.strip())
        for token, role_entry in self.role_tokens.items():
            if not token.strip():
                continue
            role = (
                role_entry[0]
                if isinstance(role_entry, tuple)
                else role_entry
            )
            if role in ("admin", "user"):
                has_configured_token = True
                break
        validate_api_auth(
            host,
            require_auth=require_auth,
            has_configured_token=has_configured_token,
        )
        self.chat_service = chat_service
        self.coding_agent = coding_agent
        self.secure_guest_cookies = secure_guest_cookies
        self.rate_limiter = rate_limiter or APIRateLimiter()
        self._thread: Thread | None = None
        self._stopped = False

        owner = self

        class Handler(BaseHTTPRequestHandler):
            timeout = 10

            def do_GET(handler):
                owner.handle_request(handler)

            def do_POST(handler):
                owner.handle_request(handler)

            def do_DELETE(handler):
                owner.handle_request(handler)

            def log_message(handler, format, *args):
                return

        self._server = ThreadingHTTPServer(
            (host, port),
            Handler,
        )
        self._server.daemon_threads = True
        self._server.block_on_close = False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        if self._stopped:
            raise RuntimeError("HTTP server cannot be restarted after stop.")
        self._thread = Thread(
            target=self._server.serve_forever,
            name="workflow-http-server",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        self._server.shutdown()
        self._server.server_close()
        if self._thread:
            self._thread.join(timeout=5)

    def handle_request(
        self,
        handler: BaseHTTPRequestHandler,
    ) -> None:
        if not self.rate_limiter.allow(
            handler.client_address[0],
        ):
            if not self._discard_request_body(handler):
                return
            self._send_json(
                handler,
                429,
                {
                    "code": "RATE_LIMITED",
                    "message": "Too many requests.",
                },
            )
            return

        parsed = urlparse(handler.path)
        path = parsed.path.rstrip("/")
        public_route = (
            handler.command == "GET"
            and path in ("", "/", "/dashboard")
        ) or (
            handler.command == "GET"
            and (path == "/chat" or path.startswith("/chat/"))
        ) or (
            handler.command == "GET"
            and (path == "/coding" or path.startswith("/coding/"))
        ) or (
            handler.command == "POST"
            and path == "/v1/chat/guest-sessions"
        ) or (
            handler.command == "GET"
            and path.startswith("/v1/coding/shared/")
        )
        chat_owner = (
            self._chat_owner(handler)
            if path.startswith("/v1/chat/")
            else None
        )
        if (
            not public_route
            and self._authenticate(handler) is None
            and chat_owner is None
        ):
            if not self._discard_request_body(handler):
                return
            self._send_json(
                handler,
                401,
                {
                    "code": "UNAUTHORIZED",
                    "message": "A valid bearer token is required.",
                },
            )
            return

        principal = self._authenticate(handler)

        try:
            if (
                handler.command == "POST"
                and path == "/v1/chat/guest-sessions"
            ):
                if not self._discard_request_body(handler):
                    return
                guest_token = self._guest_token(handler)
                response_headers = {}
                status_code = 200
                if guest_token is None:
                    guest_token = secrets.token_urlsafe(32)
                    cookie = (
                        "ai_agent_guest="
                        f"{guest_token}; Path=/; HttpOnly; SameSite=Strict; "
                        "Max-Age=2592000"
                    )
                    if self.secure_guest_cookies:
                        cookie += "; Secure"
                    response_headers["Set-Cookie"] = cookie
                    status_code = 201
                self._send_json(
                    handler,
                    status_code,
                    {"type": "guest"},
                    headers=response_headers,
                )
            elif (
                handler.command == "GET"
                and (path == "/chat" or path.startswith("/chat/"))
            ):
                self._serve_chat(handler, path)
            elif path.startswith("/v1/chat/"):
                if self.chat_service is None:
                    raise ChatError(
                        "CHAT_UNAVAILABLE",
                        "Chat service is not configured.",
                        503,
                    )
                owner_id = self._chat_owner(handler)
                if owner_id is None:
                    raise ChatError(
                        "UNAUTHORIZED",
                        "A valid user token or guest session is required.",
                        401,
                    )
                if (
                    handler.command == "GET"
                    and path == "/v1/chat/models"
                ):
                    self._send_json(
                        handler,
                        200,
                        self.chat_service.list_models(
                            refresh=(
                                parse_qs(parsed.query).get("refresh") == ["true"]
                            ),
                        ),
                    )
                elif (
                    handler.command == "GET"
                    and path == "/v1/chat/capabilities"
                ):
                    self._send_json(
                        handler,
                        200,
                        self.chat_service.capabilities(),
                    )
                elif (
                    handler.command == "GET"
                    and path == "/v1/chat/conversations"
                ):
                    self._send_json(
                        handler,
                        200,
                        {
                            "conversations":
                                self.chat_service.list_conversations(owner_id)
                        },
                    )
                elif (
                    handler.command == "POST"
                    and path == "/v1/chat/conversations"
                ):
                    body = self._read_json(handler)
                    conversation = self.chat_service.create_conversation(
                        owner_id,
                        body.get("title", "New chat"),
                    )
                    self._send_json(handler, 201, conversation)
                elif (
                    handler.command == "GET"
                    and len(path.split("/")) == 5
                    and path.startswith("/v1/chat/conversations/")
                ):
                    conversation_id = unquote(path.split("/")[4])
                    self._send_json(
                        handler,
                        200,
                        self.chat_service.get_conversation(
                            owner_id,
                            conversation_id,
                        ),
                    )
                elif (
                    handler.command == "DELETE"
                    and len(path.split("/")) == 5
                    and path.startswith("/v1/chat/conversations/")
                ):
                    conversation_id = unquote(path.split("/")[4])
                    self.chat_service.delete_conversation(
                        owner_id,
                        conversation_id,
                    )
                    self._send_json(handler, 200, {"deleted": True})
                elif (
                    handler.command == "POST"
                    and len(path.split("/")) == 6
                    and path.startswith("/v1/chat/conversations/")
                    and path.endswith("/messages")
                ):
                    parts = path.split("/")
                    conversation_id = unquote(parts[4])
                    body = self._read_json(handler)
                    result = self.chat_service.send_message(
                        owner_id,
                        conversation_id,
                        body.get("content"),
                        body.get("client_message_id"),
                        model=body.get("model"),
                        mode=body.get("mode", "chat"),
                        web_search=body.get("web_search", False),
                        search_query=body.get("search_query"),
                    )
                    self._send_json(handler, 200, result)
                else:
                    if (
                        handler.command == "POST"
                        and not self._discard_request_body(handler)
                    ):
                        return
                    self._send_json(
                        handler,
                        404,
                        {
                            "code": "NOT_FOUND",
                            "message": "Chat route not found.",
                        },
                    )
            elif (
                handler.command == "GET"
                and path.startswith("/v1/coding/shared/")
            ):
                if self.chat_service is None:
                    raise APIError(
                        "CODING_SESSION_UNAVAILABLE",
                        "Coding session storage is not configured.",
                        503,
                    )
                parts = path.split("/")
                shared = (
                    self.chat_service.store.get_shared_coding_session(parts[4])
                    if len(parts) == 5 and len(parts[4]) <= 128
                    else None
                )
                if shared is None:
                    raise APIError(
                        "SHARED_SESSION_NOT_FOUND",
                        "This shared coding session is invalid or expired.",
                        404,
                    )
                self._send_json(handler, 200, shared)
            elif path.startswith("/v1/coding/"):
                if principal is None or principal[0] != "admin":
                    if (
                        handler.command == "POST"
                        and not self._discard_request_body(handler)
                    ):
                        return
                    raise APIError(
                        "FORBIDDEN",
                        "Only administrators can use the project coding agent.",
                        403,
                    )
                if (
                    handler.command == "GET"
                    and path == "/v1/coding/projects"
                ):
                    if self.coding_agent is None:
                        raise CodingAgentError(
                            "CODING_AGENT_UNAVAILABLE",
                            "The project coding agent is not configured.",
                            503,
                        )
                    self._send_json(
                        handler,
                        200,
                        self.coding_agent.list_projects(),
                    )
                elif (
                    handler.command == "POST"
                    and path == "/v1/coding/projects"
                ):
                    if self.coding_agent is None:
                        raise CodingAgentError(
                            "CODING_AGENT_UNAVAILABLE",
                            "The project coding agent is not configured.",
                            503,
                        )
                    body = self._read_json(handler)
                    self._send_json(
                        handler,
                        201,
                        self.coding_agent.create_project(body.get("name")),
                    )
                elif (
                    handler.command == "GET"
                    and path == "/v1/coding/status"
                ):
                    self._send_json(
                        handler,
                        200,
                        {
                            "available": self.coding_agent is not None,
                            "reason": (
                                None
                                if self.coding_agent is not None
                                else "Configure AI_AGENT_CODING_WORKSPACE to enable it."
                            ),
                        },
                    )
                elif (
                    handler.command == "GET"
                    and path == "/v1/coding/files"
                ):
                    if self.coding_agent is None:
                        raise CodingAgentError(
                            "CODING_AGENT_UNAVAILABLE",
                            "The project coding agent is not configured.",
                            503,
                        )
                    self._send_json(
                        handler,
                        200,
                        self.coding_agent.list_files(
                            parse_qs(parsed.query).get("project", ["."])[0],
                        ),
                    )
                elif (
                    handler.command == "GET"
                    and path == "/v1/coding/file"
                ):
                    if self.coding_agent is None:
                        raise CodingAgentError(
                            "CODING_AGENT_UNAVAILABLE",
                            "The project coding agent is not configured.",
                            503,
                        )
                    file_path = parse_qs(parsed.query).get("path", [""])[0]
                    self._send_json(
                        handler,
                        200,
                        self.coding_agent.read_file(file_path),
                    )
                elif (
                    handler.command == "POST"
                    and path == "/v1/coding/file"
                ):
                    if self.coding_agent is None:
                        raise CodingAgentError(
                            "CODING_AGENT_UNAVAILABLE",
                            "The project coding agent is not configured.",
                            503,
                        )
                    body = self._read_json(handler)
                    self._send_json(
                        handler,
                        200,
                        self.coding_agent.write_file(
                            body.get("path"),
                            body.get("content"),
                            expected_content=body.get("expected_content"),
                            create=body.get("create", False),
                        ),
                    )
                elif (
                    handler.command == "GET"
                    and path == "/v1/coding/models"
                ):
                    if self.coding_agent is None:
                        raise CodingAgentError(
                            "CODING_AGENT_UNAVAILABLE",
                            "The project coding agent is not configured.",
                            503,
                        )
                    self._send_json(
                        handler,
                        200,
                        self.coding_agent.list_models(),
                    )
                elif (
                    handler.command == "GET"
                    and path == "/v1/coding/integrations"
                ):
                    self._send_json(
                        handler,
                        200,
                        CodingAgent.integrations(),
                    )
                elif (
                    handler.command == "GET"
                    and path == "/v1/coding/permissions"
                ):
                    if self.coding_agent is None:
                        raise CodingAgentError(
                            "CODING_AGENT_UNAVAILABLE",
                            "The project coding agent is not configured.",
                            503,
                        )
                    self._send_json(
                        handler,
                        200,
                        self.coding_agent.permissions(),
                    )
                elif (
                    handler.command == "GET"
                    and path == "/v1/coding/sessions"
                ):
                    if self.coding_agent is None or self.chat_service is None:
                        raise CodingAgentError(
                            "CODING_SESSION_UNAVAILABLE",
                            "Coding session storage is not configured.",
                            503,
                        )
                    project_id = parse_qs(parsed.query).get("project", ["."])[0]
                    project_ids = {
                        item["id"]
                        for item in self.coding_agent.list_projects()["projects"]
                    }
                    if not isinstance(project_id, str) or project_id not in project_ids:
                        raise CodingAgentError(
                            "PROJECT_NOT_FOUND",
                            "The selected project is not available in this workspace.",
                            404,
                        )
                    sessions = self.chat_service.store.list_coding_sessions(
                        self._coding_owner(principal),
                        project_id,
                    )
                    self._send_json(handler, 200, {"sessions": sessions})
                elif (
                    handler.command == "POST"
                    and path == "/v1/coding/sessions"
                ):
                    if self.coding_agent is None or self.chat_service is None:
                        raise CodingAgentError(
                            "CODING_SESSION_UNAVAILABLE",
                            "Coding session storage is not configured.",
                            503,
                        )
                    body = self._read_json(handler)
                    project_id = body.get("project_id", ".")
                    project_ids = {
                        item["id"]
                        for item in self.coding_agent.list_projects()["projects"]
                    }
                    title = body.get("title", "New session")
                    if not isinstance(project_id, str) or project_id not in project_ids:
                        raise CodingAgentError(
                            "PROJECT_NOT_FOUND",
                            "The selected project is not available in this workspace.",
                            404,
                        )
                    if not isinstance(title, str) or not title.strip() or len(title) > 120:
                        raise CodingAgentError(
                            "INVALID_SESSION_TITLE",
                            "Session titles must contain 1-120 characters.",
                            400,
                        )
                    session = self.chat_service.store.create_coding_session(
                        self._coding_owner(principal),
                        project_id,
                        title.strip(),
                    )
                    self._send_json(handler, 201, {**session, "messages": []})
                elif (
                    handler.command == "GET"
                    and len(path.split("/")) == 5
                    and path.startswith("/v1/coding/sessions/")
                ):
                    if self.chat_service is None:
                        raise CodingAgentError(
                            "CODING_SESSION_UNAVAILABLE",
                            "Coding session storage is not configured.",
                            503,
                        )
                    session = self.chat_service.store.get_coding_session(
                        self._coding_owner(principal),
                        unquote(path.split("/")[4]),
                    )
                    if session is None:
                        raise CodingAgentError(
                            "SESSION_NOT_FOUND",
                            "The coding session was not found.",
                            404,
                        )
                    self._send_json(handler, 200, session)
                elif (
                    handler.command == "POST"
                    and len(path.split("/")) == 6
                    and path.startswith("/v1/coding/sessions/")
                    and path.endswith("/share")
                ):
                    if self.chat_service is None:
                        raise CodingAgentError(
                            "CODING_SESSION_UNAVAILABLE",
                            "Coding session storage is not configured.",
                            503,
                        )
                    session_id = unquote(path.split("/")[4])
                    if not self._discard_request_body(handler):
                        return
                    share_token = secrets.token_urlsafe(32)
                    expires_at = (
                        datetime.now(timezone.utc) + timedelta(days=7)
                    ).isoformat()
                    if not self.chat_service.store.create_coding_session_share(
                        self._coding_owner(principal),
                        session_id,
                        share_token,
                        expires_at,
                    ):
                        raise CodingAgentError(
                            "SESSION_NOT_FOUND",
                            "The coding session was not found.",
                            404,
                        )
                    self._send_json(
                        handler,
                        201,
                        {"token": share_token, "expires_at": expires_at},
                    )
                elif (
                    handler.command == "DELETE"
                    and len(path.split("/")) == 6
                    and path.startswith("/v1/coding/sessions/")
                    and path.endswith("/shares")
                ):
                    if self.chat_service is None:
                        raise CodingAgentError(
                            "CODING_SESSION_UNAVAILABLE",
                            "Coding session storage is not configured.",
                            503,
                        )
                    share_count = self.chat_service.store.revoke_coding_session_shares(
                        self._coding_owner(principal),
                        unquote(path.split("/")[4]),
                    )
                    self._send_json(handler, 200, {"revoked": share_count})
                elif (
                    handler.command == "POST"
                    and path == "/v1/coding/permissions"
                ):
                    if self.coding_agent is None:
                        raise CodingAgentError(
                            "CODING_AGENT_UNAVAILABLE",
                            "The project coding agent is not configured.",
                            503,
                        )
                    body = self._read_json(handler)
                    self._send_json(
                        handler,
                        200,
                        self.coding_agent.set_permission_mode(
                            body.get("mode"),
                            confirm_auto_apply=body.get(
                                "confirm_auto_apply",
                                False,
                            ),
                            actor_id=self._coding_owner(principal),
                        ),
                    )
                elif (
                    handler.command == "GET"
                    and path == "/v1/coding/proposals"
                ):
                    if self.coding_agent is None:
                        raise CodingAgentError(
                            "CODING_AGENT_UNAVAILABLE",
                            "The project coding agent is not configured.",
                            503,
                        )
                    self._send_json(
                        handler,
                        200,
                        {
                            "proposals": self.coding_agent.list_proposals(
                                self._coding_owner(principal),
                            )
                        },
                    )
                elif (
                    handler.command == "POST"
                    and path == "/v1/coding/proposals"
                ):
                    if self.coding_agent is None:
                        raise CodingAgentError(
                            "CODING_AGENT_UNAVAILABLE",
                            "The project coding agent is not configured.",
                            503,
                        )
                    body = self._read_json(handler)
                    project_id = body.get("project_id", ".")
                    session_id = body.get("session_id")
                    session_context = None
                    session_owner = self._coding_owner(principal)
                    if self.coding_agent is None:
                        raise CodingAgentError(
                            "CODING_AGENT_UNAVAILABLE",
                            "The project coding agent is not configured.",
                            503,
                        )
                    project_ids = {
                        item["id"]
                        for item in self.coding_agent.list_projects()["projects"]
                    }
                    if not isinstance(project_id, str) or project_id not in project_ids:
                        raise CodingAgentError(
                            "PROJECT_NOT_FOUND",
                            "The selected project is not available in this workspace.",
                            404,
                        )
                    allowed_files = set(
                        self.coding_agent.list_files(project_id)["files"]
                    )
                    selected_files = body.get("files")
                    if (
                        not isinstance(selected_files, list)
                        or any(
                            not isinstance(file_name, str)
                            or file_name not in allowed_files
                            for file_name in selected_files
                        )
                    ):
                        raise CodingAgentError(
                            "INVALID_FILES",
                            "Proposals must use files from the selected project.",
                            400,
                        )
                    if session_id is not None:
                        if self.chat_service is None or not isinstance(session_id, str):
                            raise CodingAgentError(
                                "SESSION_NOT_FOUND",
                                "The coding session was not found.",
                                404,
                            )
                        session = self.chat_service.store.get_coding_session(
                            session_owner,
                            session_id,
                        )
                        if session is None:
                            raise CodingAgentError(
                                "SESSION_NOT_FOUND",
                                "The coding session was not found.",
                                404,
                            )
                        if session["project_id"] != project_id:
                            raise CodingAgentError(
                                "SESSION_PROJECT_MISMATCH",
                                "The coding session belongs to another project.",
                                400,
                            )
                        task = body.get("task")
                        if not isinstance(task, str) or not task.strip():
                            raise CodingAgentError(
                                "INVALID_TASK",
                                "A non-empty coding task is required.",
                                400,
                            )
                        session_context = session["messages"]
                        self.chat_service.store.append_coding_session_message(
                            session_owner,
                            session_id,
                            "user",
                            task.strip(),
                        )
                    else:
                        task = body.get("task")
                    self._send_json(
                        handler,
                        200,
                        self._propose_coding_change(
                            task,
                            body.get("files"),
                            body.get("model"),
                            session_context,
                            session_owner if session_id is not None else None,
                            session_id,
                            project_id,
                            session_owner,
                        ),
                    )
                elif (
                    handler.command == "POST"
                    and len(path.split("/")) == 6
                    and path.startswith("/v1/coding/proposals/")
                    and path.endswith("/apply")
                ):
                    if self.coding_agent is None:
                        raise CodingAgentError(
                            "CODING_AGENT_UNAVAILABLE",
                            "The project coding agent is not configured.",
                            503,
                        )
                    proposal_id = path.split("/")[4]
                    if not self._discard_request_body(handler):
                        return
                    self._send_json(
                        handler,
                        200,
                        self.coding_agent.apply_proposal(
                            proposal_id,
                            owner_id=self._coding_owner(principal),
                            actor_id=self._coding_owner(principal),
                        ),
                    )
                elif (
                    handler.command == "POST"
                    and len(path.split("/")) == 6
                    and path.startswith("/v1/coding/proposals/")
                    and path.endswith("/reject")
                ):
                    if self.coding_agent is None:
                        raise CodingAgentError(
                            "CODING_AGENT_UNAVAILABLE",
                            "The project coding agent is not configured.",
                            503,
                        )
                    proposal_id = path.split("/")[4]
                    if not self._discard_request_body(handler):
                        return
                    self._send_json(
                        handler,
                        200,
                        self.coding_agent.reject_proposal(
                            proposal_id,
                            owner_id=self._coding_owner(principal),
                            actor_id=self._coding_owner(principal),
                        ),
                    )
                else:
                    if (
                        handler.command == "POST"
                        and not self._discard_request_body(handler)
                    ):
                        return
                    self._send_json(
                        handler,
                        404,
                        {
                            "code": "NOT_FOUND",
                            "message": "Coding agent route not found.",
                        },
                    )
            elif handler.command == "GET" and path in ("", "/", "/dashboard"):
                self._serve_dashboard(handler)
            elif (
                handler.command == "GET"
                and (path == "/coding" or path.startswith("/coding/"))
            ):
                self._serve_chat(handler, path)
            elif handler.command == "GET" and path == "/health":
                self._send_json(
                    handler,
                    200,
                    {"status": "ok"},
                )
            elif handler.command == "GET" and path == "/v1/workflows":
                self._send_json(
                    handler,
                    200,
                    {"workflows": self.api.list_workflows()},
                )
            elif handler.command == "GET" and path == "/v1/session":
                self._send_json(
                    handler,
                    200,
                    {"role": principal[0]},
                )
            elif handler.command == "GET" and path == "/v1/runs":
                owner_id = (
                    None
                    if principal[0] == "admin"
                    else self._workflow_owner(principal)
                )
                runs = self.api.list_runs(owner_id=owner_id)
                self._send_json(handler, 200, {"runs": runs})
            elif handler.command == "POST" and path == "/v1/workflows":
                if principal[0] != "admin":
                    if not self._discard_request_body(handler):
                        return
                    raise APIError(
                        "FORBIDDEN",
                        "Only administrators can create workflows.",
                        403,
                    )
                workflow = self.api.create_workflow(
                    self._read_json(handler),
                )
                self._send_json(handler, 201, workflow)
            elif (
                handler.command == "GET"
                and path.startswith("/v1/runs/")
                and path.endswith("/events")
            ):
                run_id = path.split("/")[3]
                run = self.api.engine.get_run(run_id)
                if (
                    run is None
                    or (
                        principal[0] != "admin"
                        and run.owner_id != self._workflow_owner(principal)
                    )
                ):
                    raise APIError(
                        "RUN_NOT_FOUND",
                        f"Workflow run '{run_id}' was not found.",
                        404,
                    )
                self._stream_events(handler, run_id)
            elif (
                handler.command == "GET"
                and path.startswith("/v1/runs/")
            ):
                run_id = path.rsplit("/", 1)[-1]
                run = self.api.engine.get_run(run_id)
                if (
                    run is None
                    or (
                        principal[0] != "admin"
                        and run.owner_id != self._workflow_owner(principal)
                    )
                ):
                    raise APIError(
                        "RUN_NOT_FOUND",
                        f"Workflow run '{run_id}' was not found.",
                        404,
                    )
                self._send_json(handler, 200, self.api.get_run(run_id))
            elif (
                handler.command == "POST"
                and path.startswith("/v1/workflows/")
                and path.endswith("/runs")
            ):
                workflow_id = path.split("/")[3]
                body = self._read_json(handler)
                result = self.api.create_run(
                    workflow_id,
                    idempotency_key=self._scoped_idempotency_key(
                        body.get("idempotency_key"),
                        principal[1],
                        workflow_id,
                    ),
                    context=body.get("context"),
                    owner_id=self._workflow_owner(principal),
                )
                self._send_json(handler, 201, result)
            elif (
                handler.command == "POST"
                and path.startswith("/v1/runs/")
                and path.endswith("/cancel")
            ):
                run_id = path.split("/")[3]
                run = self.api.engine.get_run(run_id)
                if (
                    run is None
                    or (
                        principal[0] != "admin"
                        and run.owner_id != self._workflow_owner(principal)
                    )
                ):
                    if not self._discard_request_body(handler):
                        return
                    raise APIError(
                        "RUN_NOT_FOUND",
                        f"Workflow run '{run_id}' was not found.",
                        404,
                    )
                self._send_json(
                    handler,
                    200,
                    self.api.cancel_run(run_id),
                )
            elif (
                handler.command == "POST"
                and "/approvals/" in path
            ):
                if principal[0] != "admin":
                    if not self._discard_request_body(handler):
                        return
                    raise APIError(
                        "FORBIDDEN",
                        "Only administrators can decide approvals.",
                        403,
                    )
                parts = path.split("/")
                run_id = parts[3]
                node_name = unquote(parts[5])
                body = self._read_json(handler)
                if not isinstance(body.get("approved"), bool):
                    raise ValueError(
                        "Approval decision must be a boolean."
                    )
                result = self.api.decide_approval(
                    run_id,
                    node_name,
                    approved=body["approved"],
                    approver=principal[0],
                )
                self._send_json(handler, 200, result)
            else:
                if (
                    handler.command == "POST"
                    and not self._discard_request_body(handler)
                ):
                    return
                self._send_json(
                    handler,
                    404,
                    {
                        "code": "NOT_FOUND",
                        "message": "Route not found.",
                    },
                )
        except (
            APIError,
            ChatError,
            CodingAgentError,
            KeyError,
            ValueError,
        ) as exc:
            status = (
                exc.status_code
                if isinstance(exc, (APIError, ChatError, CodingAgentError))
                else 400
            )
            code = (
                exc.code
                if isinstance(exc, (APIError, ChatError, CodingAgentError))
                else "INVALID_REQUEST"
            )
            self._send_json(
                handler,
                status,
                {
                    "code": code,
                    "message": str(exc),
                },
            )

    def _scoped_idempotency_key(
        self,
        key: str | None,
        principal: str,
        workflow_id: str,
    ) -> str | None:
        if key is None:
            return None
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Idempotency key must be non-empty text.")
        principal_digest = hashlib.sha256(
            principal.encode("utf-8")
        ).hexdigest()
        return f"{principal_digest}:{workflow_id}:{key}"

    def _authorized(
        self,
        handler: BaseHTTPRequestHandler,
    ) -> bool:
        return self._authenticate(handler) is not None

    def _authenticate(
        self,
        handler: BaseHTTPRequestHandler,
    ) -> tuple[str, str] | None:
        authorization = handler.headers.get(
            "Authorization",
            "",
        )
        if not authorization:
            if (
                not self.api_token
                and not self.role_tokens
                and not self.require_auth
            ):
                return ("admin", "local")
            return None

        token = authorization[len("Bearer "):]
        if self.api_token and hmac.compare_digest(
            token,
            self.api_token,
        ):
            return ("admin", token)
        role_entry = self.role_tokens.get(token)
        if isinstance(role_entry, tuple):
            role, subject = role_entry
        else:
            role, subject = role_entry, token
        if role in ("admin", "user"):
            return (role, subject)
        return None

    def _chat_owner(
        self,
        handler: BaseHTTPRequestHandler,
    ) -> str | None:
        authorization = handler.headers.get("Authorization", "")
        if authorization:
            principal = self._authenticate(handler)
            if principal is None:
                return None
            identity = f"{principal[0]}:{principal[1]}"
        else:
            guest_token = self._guest_token(handler)
            if guest_token is not None:
                identity = f"guest:{guest_token}"
            else:
                principal = self._authenticate(handler)
                if principal is None:
                    return None
                identity = f"{principal[0]}:{principal[1]}"
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()

    @staticmethod
    def _coding_owner(principal: tuple[str, str]) -> str:
        return hashlib.sha256(
            f"coding:{principal[1]}".encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _workflow_owner(principal: tuple[str, str]) -> str:
        return hashlib.sha256(
            f"workflow:{principal[0]}:{principal[1]}".encode("utf-8")
        ).hexdigest()

    def _propose_coding_change(
        self,
        task: str,
        files: list[str],
        model: str | None,
        session_context: list[dict[str, str]] | None,
        session_owner: str | None,
        session_id: str | None,
        project_id: str,
        proposal_owner: str,
    ) -> dict:
        if self.coding_agent is None:
            raise CodingAgentError(
                "CODING_AGENT_UNAVAILABLE",
                "The project coding agent is not configured.",
                503,
            )
        result = self.coding_agent.propose(
            task,
            files,
            model=model,
            session_context=session_context,
            owner_id=proposal_owner,
            actor_id=proposal_owner,
            project_id=project_id,
            session_id=session_id,
        )
        if session_id is not None and session_owner is not None:
            message = self.chat_service.store.append_coding_session_message(
                session_owner,
                session_id,
                "assistant",
                result["proposal"],
            )
            if message is None:
                raise CodingAgentError(
                    "SESSION_NOT_FOUND",
                    "The coding session was not found.",
                    404,
                )
        result["project_id"] = project_id
        return result

    @staticmethod
    def _guest_token(
        handler: BaseHTTPRequestHandler,
    ) -> str | None:
        cookie = SimpleCookie()
        try:
            cookie.load(handler.headers.get("Cookie", ""))
        except CookieError:
            return None
        guest_cookie = cookie.get("ai_agent_guest")
        if guest_cookie is None:
            return None
        value = guest_cookie.value
        if (
            len(value) < 32
            or len(value) > 100
            or re.fullmatch(r"[A-Za-z0-9_-]+", value) is None
        ):
            return None
        return value

    def _read_json(
        self,
        handler: BaseHTTPRequestHandler,
    ) -> dict:
        try:
            length = int(handler.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Invalid Content-Length header.") from exc
        if length > 1_048_576:
            raise ValueError("Request body exceeds 1 MiB.")
        if length <= 0:
            return {}
        raw = handler.rfile.read(length)
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Request body must be valid JSON."
            ) from exc
        if not isinstance(result, dict):
            raise ValueError(
                "Request body must be a JSON object."
            )
        return result

    def _discard_request_body(
        self,
        handler: BaseHTTPRequestHandler,
    ) -> bool:
        try:
            length = int(handler.headers.get("Content-Length", "0"))
        except ValueError:
            handler.close_connection = True
            return False
        if length <= 0:
            return True
        if length > 1_048_576:
            handler.close_connection = True
            return False
        try:
            remaining = length
            while remaining:
                chunk = handler.rfile.read(min(remaining, 64 * 1024))
                if not chunk:
                    handler.close_connection = True
                    return False
                remaining -= len(chunk)
            return True
        except OSError:
            handler.close_connection = True
            return False

    def _send_json(
        self,
        handler: BaseHTTPRequestHandler,
        status: int,
        payload: dict,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        body = json.dumps(payload).encode("utf-8")
        handler.send_response(status)
        handler.send_header(
            "Content-Type",
            "application/json",
        )
        handler.send_header("Cache-Control", "no-store")
        handler.send_header(
            "Content-Length",
            str(len(body)),
        )
        for name, value in (headers or {}).items():
            handler.send_header(name, value)
        handler.end_headers()
        handler.wfile.write(body)

    def _serve_chat(
        self,
        handler: BaseHTTPRequestHandler,
        path: str,
    ) -> None:
        build_root = (
            Path(__file__).resolve().parents[2]
            / "frontend"
            / "dist"
        ).resolve()
        if (
            path in ("/chat", "/coding")
            or path.startswith("/coding/share/")
        ):
            asset_path = build_root / "index.html"
        else:
            relative_path = path.removeprefix("/chat/").strip("/")
            asset_path = (build_root / relative_path).resolve()
            if build_root not in asset_path.parents:
                self._send_json(
                    handler,
                    404,
                    {
                        "code": "CHAT_ASSET_NOT_FOUND",
                        "message": "Chat frontend asset was not found.",
                    },
                )
                return
        if not asset_path.is_file():
            self._send_json(
                handler,
                404,
                {
                    "code": "CHAT_FRONTEND_NOT_FOUND",
                    "message": "Build the React chat frontend before serving it.",
                },
            )
            return
        body = asset_path.read_bytes()
        content_type = mimetypes.guess_type(asset_path.name)[0]
        handler.send_response(200)
        handler.send_header(
            "Content-Type",
            content_type or "application/octet-stream",
        )
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header(
            "Cache-Control",
            "no-cache" if asset_path.name == "index.html"
            else "public, max-age=31536000, immutable",
        )
        handler.end_headers()
        handler.wfile.write(body)

    def _serve_dashboard(
        self,
        handler: BaseHTTPRequestHandler,
    ) -> None:
        html_path = (
            Path(__file__).resolve().parents[2]
            / "frontend"
            / "index.html"
        )
        if not html_path.exists():
            self._send_json(
                handler,
                404,
                {
                    "code": "FRONTEND_NOT_FOUND",
                    "message": "Frontend assets are unavailable.",
                },
            )
            return

        body = html_path.read_bytes()
        handler.send_response(200)
        handler.send_header("Content-Type", "text/html; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("Cache-Control", "no-cache")
        handler.end_headers()
        handler.wfile.write(body)

    def _stream_events(
        self,
        handler: BaseHTTPRequestHandler,
        run_id: str,
    ) -> None:
        subscription_id = self.event_bus.subscribe(
            run_id,
        )
        handler.send_response(200)
        handler.send_header(
            "Content-Type",
            "text/event-stream",
        )
        handler.send_header(
            "Cache-Control",
            "no-cache",
        )
        handler.send_header(
            "Connection",
            "close",
        )
        handler.close_connection = True
        handler.end_headers()

        try:
            run = self.api.engine.get_run(run_id)
            if run is None:
                return

            initial_event = WorkflowEvent(
                run_id=run.id,
                event_type="workflow.status",
                payload={
                    "run_id": run.id,
                    "workflow_id": run.workflow_id,
                    "status": run.status.value,
                    "node_statuses": {
                        name: status.value
                        for name, status in run.node_statuses.items()
                    },
                },
            )
            handler.wfile.write(
                (
                    "event: workflow.status\n"
                    f"data: {json.dumps(initial_event.to_dict())}\n\n"
                ).encode("utf-8")
            )
            handler.wfile.flush()
            if run.status.value in (
                "completed",
                "failed",
                "cancelled",
            ):
                return

            next_heartbeat = time.monotonic() + 15
            while True:
                events = self.event_bus.consume(
                    subscription_id,
                    limit=100,
                )
                terminal = False
                for event in events:
                    payload = json.dumps(
                        event.to_dict(),
                    )
                    handler.wfile.write(
                        f"event: {event.event_type}\n"
                        f"data: {payload}\n\n".encode(
                            "utf-8"
                        )
                    )
                    handler.wfile.flush()
                    if event.payload.get("status") in (
                        "completed",
                        "failed",
                        "cancelled",
                    ):
                        terminal = True
                if terminal:
                    return
                if time.monotonic() >= next_heartbeat:
                    handler.wfile.write(b": keep-alive\n\n")
                    handler.wfile.flush()
                    next_heartbeat = time.monotonic() + 15
                time.sleep(0.05)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            self.event_bus.unsubscribe(subscription_id)
