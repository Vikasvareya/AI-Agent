import json
import os
import time
import hashlib
import hmac
import mimetypes
import re
import secrets
import csv
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock, Thread
from urllib.parse import parse_qs, unquote, urlparse
from uuid import uuid4

from app.agents.coding_agent import CodingAgent, CodingAgentError
from app.agents.coordinator import (
    CoordinatorAgent,
    DelegationPermissionPolicy,
)
from app.api.security_config import validate_api_auth
from app.api.workflow_service import APIError, WorkflowAPIService
from app.chat.service import ChatError, ChatService
from app.realtime.event_bus import EventBus
from app.realtime.models import WorkflowEvent
from app.research.page_fetcher import (
    PageFetcher,
    PageFetchError,
    UnsafeUrlError,
)
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
        allowed_origins: tuple[str, ...] = (),
        delegation_coordinator: CoordinatorAgent | None = None,
        delegation_policy: DelegationPermissionPolicy | None = None,
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
        self.allowed_origins = tuple(
            origin.rstrip("/")
            for origin in allowed_origins
            if origin.strip()
        )
        self.delegation_coordinator = delegation_coordinator
        self.delegation_policy = delegation_policy
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

            def do_PATCH(handler):
                owner.handle_request(handler)

            def do_OPTIONS(handler):
                owner.handle_options(handler)

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
        if not self._origin_allowed(handler):
            if not self._discard_request_body(handler):
                return
            self._send_json(
                handler,
                403,
                {
                    "code": "ORIGIN_NOT_ALLOWED",
                    "message": "This request origin is not allowed.",
                },
            )
            return
        client_id = handler.client_address[0]
        if self.chat_service is not None:
            allowed = self.chat_service.store.allow_distributed_request(
                client_id,
                self.rate_limiter.max_requests,
                self.rate_limiter.window_seconds,
            )
        else:
            allowed = self.rate_limiter.allow(client_id)
        if not allowed:
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

        if (
            handler.command == "GET"
            and (
                path == "/chat"
                or path.startswith("/chat/")
                or path == "/coding"
                or path.startswith("/coding/")
            )
        ):
            self._serve_chat(handler, path)
            return

        try:
            if handler.command == "GET" and path == "/v1/research/status":
                if self.chat_service is None:
                    raise APIError("RESEARCH_UNAVAILABLE", "Research service is unavailable.", 503)
                status = (
                    self.chat_service.search_manager.provider_status()
                    if self.chat_service.search_manager is not None
                    else {
                        "active_mode": "brave",
                        "brave": {
                            "configured": bool(
                                self.chat_service.web_search_provider
                                and self.chat_service.web_search_provider.available
                            ),
                            "healthy": bool(
                                self.chat_service.web_search_provider
                                and self.chat_service.web_search_provider.available
                            ),
                        },
                        "searxng": {"configured": False, "healthy": False},
                    }
                )
                self._send_json(handler, 200, {"providers": status})
            elif (
                handler.command == "POST"
                and path == "/v1/research/search"
            ):
                if self.chat_service is None:
                    raise APIError("RESEARCH_UNAVAILABLE", "Research service is unavailable.", 503)
                body = self._read_json(handler)
                query = body.get("query")
                limit = body.get("limit", 5)
                if not isinstance(query, str) or not query.strip():
                    raise APIError("INVALID_SEARCH", "A search query is required.", 400)
                if not isinstance(limit, int):
                    raise APIError("INVALID_SEARCH", "Result limit must be an integer.", 400)
                try:
                    if self.chat_service.search_manager is not None:
                        results = self.chat_service.search_manager.search(query, limit=limit)
                    else:
                        results = [
                            source
                            for source in self.chat_service.web_search_provider.search(
                                query,
                                limit=max(1, min(limit, 10)),
                            )
                        ]
                except Exception as exc:
                    raise APIError("SEARCH_UNAVAILABLE", str(exc), 502)
                self._send_json(handler, 200, {"query": query, "results": results})
            elif (
                handler.command == "POST"
                and path == "/v1/research/fetch"
            ):
                body = self._read_json(handler)
                url = body.get("url")
                if not isinstance(url, str) or not url.strip():
                    raise APIError("INVALID_SOURCE", "A source URL is required.", 400)
                try:
                    fetched = PageFetcher().fetch(url)
                except UnsafeUrlError as exc:
                    raise APIError("UNSAFE_SOURCE", str(exc), 400)
                except PageFetchError as exc:
                    raise APIError("SOURCE_FETCH_FAILED", str(exc), 502)
                self._send_json(handler, 200, {"source": fetched})
            if (
                handler.command == "GET"
                and path == "/v1/memory/history"
            ):
                if self.chat_service is None:
                    raise APIError("MEMORY_UNAVAILABLE", "Memory service is unavailable.", 503)
                owner_id = self._chat_owner(handler)
                if owner_id is None:
                    raise APIError("UNAUTHORIZED", "A valid owner session is required.", 401)
                record_id = parse_qs(parsed.query).get("record_id", [None])[0]
                self._send_json(
                    handler,
                    200,
                    {"history": self.chat_service.store.list_memory_history(owner_id, record_id)},
                )
            elif (
                handler.command == "GET"
                and (
                    path == "/v1/memory/profile"
                    or path == "/v1/memory/records"
                )
            ):
                if self.chat_service is None:
                    raise APIError("MEMORY_UNAVAILABLE", "Memory service is unavailable.", 503)
                owner_id = self._chat_owner(handler)
                if owner_id is None:
                    raise APIError("UNAUTHORIZED", "A valid owner session is required.", 401)
                status = parse_qs(parsed.query).get("status", [None])[0]
                query = parse_qs(parsed.query).get("query", [None])[0]
                limit = int(parse_qs(parsed.query).get("limit", ["100"])[0])
                records = self.chat_service.store.list_memory_records(
                    owner_id,
                    status=status,
                    limit=limit,
                    query=query,
                )
                self._send_json(
                    handler,
                    200,
                    {
                        "profile": records if path == "/v1/memory/profile" else None,
                        "records": records,
                    },
                )
            elif (
                handler.command == "POST"
                and path == "/v1/memory/records"
            ):
                if self.chat_service is None:
                    raise APIError("MEMORY_UNAVAILABLE", "Memory service is unavailable.", 503)
                owner_id = self._chat_owner(handler)
                if owner_id is None:
                    raise APIError("UNAUTHORIZED", "A valid owner session is required.", 401)
                body = self._read_json(handler)
                category = body.get("category")
                key = body.get("key")
                value = body.get("value")
                if not all(isinstance(item, str) and item.strip() for item in (category, key, value)):
                    raise APIError("INVALID_MEMORY", "category, key, and value are required.", 400)
                if len(category) > 80 or len(key) > 120 or len(value) > 2000:
                    raise APIError("INVALID_MEMORY", "Memory fields exceed supported lengths.", 400)
                record = self.chat_service.store.save_memory_record(
                    owner_id,
                    conversation_id=None,
                    category=category.strip(),
                    key=key.strip(),
                    value=value.strip(),
                    source="authorized_profile_import",
                    confidence=1.0,
                    status="confirmed",
                    metadata=body.get("metadata") if isinstance(body.get("metadata"), dict) else {},
                    expires_at=body.get("expires_at") if isinstance(body.get("expires_at"), str) else None,
                )
                self._send_json(handler, 201, {"record": record})
            elif (
                handler.command == "GET"
                and path == "/v1/resume/drafts"
            ):
                if self.chat_service is None:
                    raise APIError("RESUME_UNAVAILABLE", "Resume service is unavailable.", 503)
                owner_id = self._chat_owner(handler)
                if owner_id is None:
                    raise APIError("UNAUTHORIZED", "A valid owner session is required.", 401)
                self._send_json(
                    handler,
                    200,
                    {"drafts": self.chat_service.store.list_resume_drafts(owner_id)},
                )
            elif (
                handler.command == "POST"
                and path == "/v1/resume/drafts"
            ):
                if self.chat_service is None:
                    raise APIError("RESUME_UNAVAILABLE", "Resume service is unavailable.", 503)
                owner_id = self._chat_owner(handler)
                if owner_id is None:
                    raise APIError("UNAUTHORIZED", "A valid owner session is required.", 401)
                body = self._read_json(handler)
                title = body.get("title")
                content = body.get("content")
                status = body.get("status", "draft")
                if not isinstance(title, str) or not title.strip():
                    raise APIError("INVALID_RESUME", "A resume title is required.", 400)
                if not isinstance(content, str) or not content.strip():
                    raise APIError("INVALID_RESUME", "Resume content is required.", 400)
                draft = self.chat_service.store.save_resume_draft(
                    owner_id,
                    title=title,
                    content=content,
                    status=status if status in ("draft", "edited", "approved") else "draft",
                )
                self._send_json(handler, 201, {"draft": draft})
            elif (
                path.startswith("/v1/resume/drafts/")
                and len(path.split("/")) >= 5
            ):
                if self.chat_service is None:
                    raise APIError("RESUME_UNAVAILABLE", "Resume service is unavailable.", 503)
                owner_id = self._chat_owner(handler)
                if owner_id is None:
                    raise APIError("UNAUTHORIZED", "A valid owner session is required.", 401)
                parts = path.split("/")
                draft_id = unquote(parts[4])
                if len(parts) == 6 and parts[5] == "export":
                    draft = self.chat_service.store.get_resume_draft(owner_id, draft_id)
                    if draft is None:
                        raise APIError("RESUME_NOT_FOUND", "Resume draft was not found.", 404)
                    self._send_json(
                        handler,
                        200,
                        {"format": "text", "filename": f"{draft['title']}.txt", "content": draft["content"]},
                    )
                elif len(parts) == 5 and handler.command == "GET":
                    draft = self.chat_service.store.get_resume_draft(owner_id, draft_id)
                    if draft is None:
                        raise APIError("RESUME_NOT_FOUND", "Resume draft was not found.", 404)
                    self._send_json(handler, 200, {"draft": draft})
                elif len(parts) == 5 and handler.command in ("PATCH", "POST"):
                    body = self._read_json(handler)
                    existing = self.chat_service.store.get_resume_draft(owner_id, draft_id)
                    if existing is None:
                        raise APIError("RESUME_NOT_FOUND", "Resume draft was not found.", 404)
                    draft = self.chat_service.store.save_resume_draft(
                        owner_id,
                        draft_id=draft_id,
                        title=body.get("title", existing["title"]),
                        content=body.get("content", existing["content"]),
                        status=body.get("status", existing["status"]),
                    )
                    self._send_json(handler, 200, {"draft": draft})
                elif len(parts) == 5 and handler.command == "DELETE":
                    if not self.chat_service.store.delete_resume_draft(owner_id, draft_id):
                        raise APIError("RESUME_NOT_FOUND", "Resume draft was not found.", 404)
                    self._send_json(handler, 200, {"deleted": True})
                else:
                    raise APIError("NOT_FOUND", "Resume route not found.", 404)
            elif (
                handler.command == "POST"
                and path == "/v1/memory/profile/clear"
            ):
                if self.chat_service is None:
                    raise APIError("MEMORY_UNAVAILABLE", "Memory service is unavailable.", 503)
                owner_id = self._chat_owner(handler)
                if owner_id is None:
                    raise APIError("UNAUTHORIZED", "A valid owner session is required.", 401)
                count = self.chat_service.store.clear_memory_records(owner_id)
                self._send_json(handler, 200, {"deleted": count})
            elif (
                path.startswith("/v1/memory/records/")
                and len(path.split("/")) == 5
            ):
                if self.chat_service is None:
                    raise APIError("MEMORY_UNAVAILABLE", "Memory service is unavailable.", 503)
                owner_id = self._chat_owner(handler)
                if owner_id is None:
                    raise APIError("UNAUTHORIZED", "A valid owner session is required.", 401)
                record_id = unquote(path.split("/")[4])
                if handler.command == "GET":
                    record = self.chat_service.store.get_memory_record(owner_id, record_id)
                    if record is None:
                        raise APIError("MEMORY_NOT_FOUND", "Memory record was not found.", 404)
                    self._send_json(handler, 200, {"record": record})
                elif handler.command == "PATCH":
                    body = self._read_json(handler)
                    record = self.chat_service.store.update_memory_record(
                        owner_id,
                        record_id,
                        value=body.get("value") if isinstance(body.get("value"), str) else None,
                        category=body.get("category") if isinstance(body.get("category"), str) else None,
                        key=body.get("key") if isinstance(body.get("key"), str) else None,
                        status=body.get("status") if isinstance(body.get("status"), str) else None,
                        expires_at=body.get("expires_at") if isinstance(body.get("expires_at"), str) else None,
                        metadata=body.get("metadata") if isinstance(body.get("metadata"), dict) else None,
                    )
                    if record is None:
                        raise APIError("MEMORY_NOT_FOUND", "Memory record was not found.", 404)
                    self._send_json(handler, 200, {"record": record})
                elif handler.command == "DELETE":
                    deleted = self.chat_service.store.delete_memory_record(owner_id, record_id)
                    if not deleted:
                        raise APIError("MEMORY_NOT_FOUND", "Memory record was not found.", 404)
                    self._send_json(handler, 200, {"deleted": True})
                else:
                    if not self._discard_request_body(handler):
                        return
                    raise APIError("METHOD_NOT_ALLOWED", "Unsupported memory operation.", 405)
            if (
                handler.command == "POST"
                and path == "/v1/agents/delegate"
            ):
                if self.delegation_coordinator is None:
                    raise APIError(
                        "DELEGATION_UNAVAILABLE",
                        "Multi-agent delegation is not configured.",
                        503,
                    )
                body = self._read_json(handler)
                agents = body.get("agents")
                prompt = body.get("prompt")
                if not isinstance(agents, list) or not agents or any(
                    not isinstance(name, str) or not name.strip()
                    for name in agents
                ):
                    raise APIError(
                        "INVALID_DELEGATION",
                        "agents must be a non-empty list of agent names.",
                        400,
                    )
                owner_id = self._delegation_owner(principal)
                try:
                    if body.get("async") is True:
                        if self.chat_service is None:
                            raise APIError(
                                "DELEGATION_UNAVAILABLE",
                                "Durable agent task storage is not configured.",
                                503,
                            )
                        result = self.delegation_coordinator.enqueue(
                            owner_id,
                            principal[0],
                            [name.strip() for name in agents],
                            prompt,
                            policy=self.delegation_policy,
                            persistence_store=self.chat_service.store,
                        )
                        response_status = 202
                    else:
                        result = self.delegation_coordinator.delegate(
                            owner_id,
                            principal[0],
                            [name.strip() for name in agents],
                            prompt,
                            policy=self.delegation_policy,
                            persistence_store=(
                                self.chat_service.store
                                if self.chat_service is not None
                                else None
                            ),
                            max_parallel=int(body.get("max_parallel", 8)),
                        )
                        response_status = 202
                except PermissionError as exc:
                    raise APIError("DELEGATION_FORBIDDEN", str(exc), 403)
                except ValueError as exc:
                    raise APIError("INVALID_DELEGATION", str(exc), 400)
                task_ids = [task["id"] for task in result["tasks"]]
                self._record_audit(
                    principal,
                    "agent_tasks_delegated",
                    task_ids[0] if len(task_ids) == 1 else None,
                    {
                        "task_ids": task_ids,
                        "agents": [name.strip() for name in agents],
                        "aggregation_status": result["aggregation"]["status"],
                    },
                )
                self._send_json(handler, 202, result)
            elif (
                handler.command == "GET"
                and path == "/v1/agent-tasks"
            ):
                if self.chat_service is None:
                    raise APIError(
                        "DELEGATION_UNAVAILABLE",
                        "Durable agent task storage is not configured.",
                        503,
                    )
                owner_id = self._delegation_owner(principal)
                limit = int(parse_qs(parsed.query).get("limit", ["100"])[0])
                self._send_json(
                    handler,
                    200,
                    {
                        "tasks": self.chat_service.store.list_delegation_tasks(
                            owner_id,
                            limit,
                        )
                    },
                )
            elif (
                handler.command == "POST"
                and path.startswith("/v1/agent-tasks/")
                and path.endswith("/cancel")
            ):
                if self.chat_service is None:
                    raise APIError(
                        "DELEGATION_UNAVAILABLE",
                        "Durable agent task storage is not configured.",
                        503,
                    )
                task_id = path.split("/")[3]
                owner_id = self._delegation_owner(principal)
                cancelled = self.chat_service.store.cancel_delegation_task(
                    owner_id,
                    task_id,
                )
                if not cancelled:
                    raise APIError(
                        "AGENT_TASK_NOT_CANCELLABLE",
                        f"Agent task '{task_id}' cannot be cancelled.",
                        409,
                    )
                self._send_json(handler, 200, {"cancelled": True, "id": task_id})
            elif (
                handler.command == "GET"
                and path.startswith("/v1/agent-tasks/")
            ):
                if self.chat_service is None:
                    raise APIError(
                        "DELEGATION_UNAVAILABLE",
                        "Durable agent task storage is not configured.",
                        503,
                    )
                task_id = path.rsplit("/", 1)[-1]
                owner_id = self._delegation_owner(principal)
                task = self.chat_service.store.get_delegation_task(
                    owner_id,
                    task_id,
                )
                if task is None:
                    raise APIError(
                        "AGENT_TASK_NOT_FOUND",
                        f"Agent task '{task_id}' was not found.",
                        404,
                    )
                task["messages"] = self.chat_service.store.list_delegation_messages(
                    owner_id,
                    task_id,
                )
                self._send_json(handler, 200, task)
            elif (
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
                and (
                    path == "/chat"
                    or path.startswith("/chat/")
                    or path == "/coding"
                    or path.startswith("/coding/")
                )
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
                    and len(path.split("/")) == 7
                    and path.startswith("/v1/chat/conversations/")
                    and path.endswith("/activity/events")
                ):
                    parts = path.split("/")
                    conversation_id = unquote(parts[4])
                    if self.chat_service.get_conversation(
                        owner_id,
                        conversation_id,
                    ) is None:
                        raise ChatError(
                            "CONVERSATION_NOT_FOUND",
                            "Conversation was not found.",
                            404,
                        )
                    run_id = parse_qs(parsed.query).get("run_id", [None])[0]
                    self._stream_activity_events(
                        handler,
                        owner_id,
                        conversation_id,
                        run_id,
                    )
                elif (
                    handler.command == "GET"
                    and len(path.split("/")) == 6
                    and path.startswith("/v1/chat/conversations/")
                    and path.endswith("/activity")
                ):
                    parts = path.split("/")
                    conversation_id = unquote(parts[4])
                    run_id = parse_qs(parsed.query).get("run_id", [None])[0]
                    if self.chat_service.get_conversation(
                        owner_id,
                        conversation_id,
                    ) is None:
                        raise ChatError(
                            "CONVERSATION_NOT_FOUND",
                            "Conversation was not found.",
                            404,
                        )
                    self._send_json(
                        handler,
                        200,
                        {
                            "events": self.chat_service.store.list_activity_events(
                                owner_id,
                                conversation_id,
                                run_id=run_id,
                            )
                        },
                    )
                elif (
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
                        run_id=body.get("run_id"),
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
                    and path == "/v1/coding/directories"
                ):
                    if self.coding_agent is None:
                        raise CodingAgentError(
                            "CODING_AGENT_UNAVAILABLE",
                            "The project coding agent is not configured.",
                            503,
                        )
                    directory_path = parse_qs(parsed.query).get("path", [None])[0]
                    self._send_json(
                        handler,
                        200,
                        self.coding_agent.list_directories(directory_path),
                    )
                elif (
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
                    project = self.coding_agent.create_project(
                        body.get("name"),
                        parent_path=body.get("parent_path"),
                    )
                    self._record_audit(
                        principal,
                        "coding_project_created",
                        project.get("id"),
                        {"location": project.get("location")},
                    )
                    self._send_json(
                        handler,
                        201,
                        project,
                    )
                elif (
                    handler.command == "POST"
                    and path == "/v1/coding/projects/import"
                ):
                    if self.coding_agent is None:
                        raise CodingAgentError(
                            "CODING_AGENT_UNAVAILABLE",
                            "The project coding agent is not configured.",
                            503,
                        )
                    body = self._read_json(handler)
                    project = self.coding_agent.import_project(body.get("path"))
                    self._record_audit(
                        principal,
                        "coding_project_imported",
                        project.get("id"),
                        {"location": project.get("location")},
                    )
                    self._send_json(handler, 200, project)
                elif (
                    handler.command == "DELETE"
                    and len(path.split("/")) == 5
                    and path.startswith("/v1/coding/projects/")
                ):
                    if self.coding_agent is None:
                        raise CodingAgentError(
                            "CODING_AGENT_UNAVAILABLE",
                            "The project coding agent is not configured.",
                            503,
                        )
                    project_id = unquote(path.split("/")[4])
                    deleted_project = self.coding_agent.delete_project(
                        project_id
                    )
                    deleted_sessions = (
                        self.chat_service.store.delete_coding_sessions_for_project(
                            project_id,
                            self._coding_owner(principal),
                        )
                        if self.chat_service is not None
                        else 0
                    )
                    self._record_audit(
                        principal,
                        "coding_project_deleted",
                        project_id,
                        {
                            "deleted_conversations": deleted_sessions,
                            "files_deleted": deleted_project.get(
                                "files_deleted",
                                False,
                            ),
                        },
                    )
                    self._send_json(
                        handler,
                        200,
                        {
                            **deleted_project,
                            "deleted_conversations": deleted_sessions,
                        },
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
                    result = self.coding_agent.write_file(
                        body.get("path"),
                        body.get("content"),
                        expected_content=body.get("expected_content"),
                        create=body.get("create", False),
                    )
                    self._record_audit(
                        principal,
                        "coding_file_written",
                        body.get("path"),
                        {
                            "create": body.get("create", False),
                        },
                    )
                    self._send_json(
                        handler,
                        200,
                        result,
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
                    and path == "/v1/coding/audit"
                ):
                    if self.coding_agent is None:
                        raise CodingAgentError(
                            "CODING_AGENT_UNAVAILABLE",
                            "The project coding agent is not configured.",
                            503,
                        )
                    query = parse_qs(
                        parsed.query,
                        keep_blank_values=True,
                    )
                    limit = self._audit_query_integer(
                        query,
                        "limit",
                        default=50,
                        minimum=1,
                        maximum=100,
                    )
                    offset = self._audit_query_integer(
                        query,
                        "offset",
                        default=0,
                        minimum=0,
                        maximum=10_000,
                    )
                    events = self.coding_agent.list_audit_events(
                        limit + 1,
                        offset,
                    )
                    has_more = len(events) > limit
                    self._send_json(
                        handler,
                        200,
                        {
                            "events": events[:limit],
                            "limit": limit,
                            "offset": offset,
                            "has_more": has_more,
                        },
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
                    self._record_audit(
                        principal,
                        "coding_session_created",
                        session["id"],
                        {"project_id": project_id},
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
                    handler.command == "DELETE"
                    and len(path.split("/")) == 5
                    and path.startswith("/v1/coding/sessions/")
                ):
                    if self.chat_service is None:
                        raise CodingAgentError(
                            "CODING_SESSION_UNAVAILABLE",
                            "Coding session storage is not configured.",
                            503,
                        )
                    session_id = unquote(path.split("/")[4])
                    if not self.chat_service.store.delete_coding_session(
                        self._coding_owner(principal),
                        session_id,
                        self._coding_owner(principal),
                    ):
                        raise CodingAgentError(
                            "SESSION_NOT_FOUND",
                            "The coding conversation was not found.",
                            404,
                        )
                    self._record_audit(
                        principal,
                        "coding_session_deleted",
                        session_id,
                        {},
                    )
                    self._send_json(
                        handler,
                        200,
                        {"id": session_id, "deleted": True},
                    )
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
                    self._record_audit(
                        principal,
                        "coding_session_shared",
                        session_id,
                        {"expires_at": expires_at},
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
                    self._record_audit(
                        principal,
                        "coding_session_shares_revoked",
                        unquote(path.split("/")[4]),
                        {"revoked": share_count},
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
                    result = self.coding_agent.set_permission_mode(
                        body.get("mode"),
                        confirm_auto_apply=body.get(
                            "confirm_auto_apply",
                            False,
                        ),
                        actor_id=self._coding_owner(principal),
                    )
                    self._send_json(
                        handler,
                        200,
                        result,
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
            elif handler.command == "GET" and path == "/v1/audit":
                if principal[0] != "admin":
                    raise APIError(
                        "FORBIDDEN",
                        "Only administrators can inspect audit events.",
                        403,
                    )
                if self.chat_service is None:
                    raise APIError(
                        "AUDIT_UNAVAILABLE",
                        "Audit event storage is not configured.",
                        503,
                    )
                query = parse_qs(parsed.query, keep_blank_values=True)
                limit = self._audit_query_integer(
                    query,
                    "limit",
                    default=50,
                    minimum=1,
                    maximum=100,
                )
                offset = self._audit_query_integer(
                    query,
                    "offset",
                    default=0,
                    minimum=0,
                    maximum=10_000,
                )
                action_values = query.get("action", [])
                action = action_values[0] if len(action_values) == 1 else None
                if len(action_values) > 1:
                    raise APIError(
                        "INVALID_AUDIT_QUERY",
                        "The action filter must appear once.",
                        400,
                    )
                if action is not None and (
                    not action.strip()
                    or len(action) > 128
                ):
                    raise APIError(
                        "INVALID_AUDIT_QUERY",
                        "The action filter must contain 1-128 characters.",
                        400,
                    )
                events = self.chat_service.store.list_audit(
                    limit + 1,
                    offset,
                    action,
                )
                self._send_json(
                    handler,
                    200,
                    {
                        "events": events[:limit],
                        "limit": limit,
                        "offset": offset,
                        "has_more": len(events) > limit,
                    },
                )
            elif handler.command == "GET" and path == "/v1/audit/summary":
                if principal[0] != "admin":
                    raise APIError(
                        "FORBIDDEN",
                        "Only administrators can inspect audit summaries.",
                        403,
                    )
                if self.chat_service is None:
                    raise APIError(
                        "AUDIT_UNAVAILABLE",
                        "Audit event storage is not configured.",
                        503,
                    )
                events = self.chat_service.store.list_audit(1000)
                action_counts: dict[str, int] = {}
                for event in events:
                    action = event["action"]
                    action_counts[action] = action_counts.get(action, 0) + 1
                sensitive_actions = (
                    "api_credential_created",
                    "api_credential_rotated",
                    "api_credential_revoked",
                    "coding_permission_mode_set",
                    "workflow_approval_decided",
                )
                sensitive_events = [
                    event
                    for event in events
                    if event["action"] in sensitive_actions
                ]
                self._send_json(
                    handler,
                    200,
                    {
                        "events_scanned": len(events),
                        "action_counts": action_counts,
                        "sensitive_event_count": len(sensitive_events),
                        "security_alert": len(sensitive_events) > 0,
                        "sensitive_events": sensitive_events[:50],
                    },
                )
            elif handler.command == "GET" and path == "/v1/audit/export":
                if principal[0] != "admin":
                    raise APIError(
                        "FORBIDDEN",
                        "Only administrators can export audit events.",
                        403,
                    )
                if self.chat_service is None:
                    raise APIError(
                        "AUDIT_UNAVAILABLE",
                        "Audit event storage is not configured.",
                        503,
                    )
                query = parse_qs(parsed.query, keep_blank_values=True)
                limit = self._audit_query_integer(
                    query,
                    "limit",
                    default=100,
                    minimum=1,
                    maximum=1000,
                )
                action_values = query.get("action", [])
                action = action_values[0] if len(action_values) == 1 else None
                if len(action_values) > 1:
                    raise APIError(
                        "INVALID_AUDIT_QUERY",
                        "The action filter must appear once.",
                        400,
                    )
                format_values = query.get("format", ["json"])
                if len(format_values) != 1 or format_values[0] not in ("json", "csv"):
                    raise APIError(
                        "INVALID_AUDIT_FORMAT",
                        "Audit export format must be 'json' or 'csv'.",
                        400,
                    )
                events = self.chat_service.store.list_audit(
                    limit,
                    0,
                    action,
                )
                if format_values[0] == "json":
                    body = json.dumps(
                        events,
                        indent=2,
                        sort_keys=True,
                    ).encode("utf-8")
                    content_type = "application/json"
                    filename = "audit-events.json"
                else:
                    buffer = io.StringIO(newline="")
                    writer = csv.DictWriter(
                        buffer,
                        fieldnames=[
                            "id",
                            "actor_id",
                            "action",
                            "resource_id",
                            "details",
                            "created_at",
                        ],
                    )
                    writer.writeheader()
                    for event in events:
                        writer.writerow({
                            **event,
                            "details": json.dumps(
                                event["details"],
                                sort_keys=True,
                                separators=(",", ":"),
                            ),
                        })
                    body = buffer.getvalue().encode("utf-8")
                    content_type = "text/csv"
                    filename = "audit-events.csv"
                self._send_export(
                    handler,
                    body,
                    content_type,
                    filename,
                )
            elif handler.command == "GET" and path == "/v1/auth/credentials":
                if principal[0] != "admin":
                    raise APIError(
                        "FORBIDDEN",
                        "Only administrators can inspect credentials.",
                        403,
                    )
                if self.chat_service is None:
                    raise APIError(
                        "CREDENTIAL_STORAGE_UNAVAILABLE",
                        "Credential storage is not configured.",
                        503,
                    )
                now = datetime.now(timezone.utc).isoformat()
                credentials = []
                for credential in self.chat_service.store.list_api_credentials():
                    if credential["revoked_at"] is not None:
                        status = "revoked"
                    elif credential["expires_at"] <= now:
                        status = "expired"
                    else:
                        status = "active"
                    credentials.append({
                        "id": credential["id"],
                        "role": credential["role"],
                        "subject": credential["subject"],
                        "expires_at": credential["expires_at"],
                        "revoked_at": credential["revoked_at"],
                        "created_at": credential["created_at"],
                        "status": status,
                    })
                self._send_json(
                    handler,
                    200,
                    {"credentials": credentials},
                )
            elif handler.command == "POST" and path == "/v1/auth/credentials":
                if principal[0] != "admin":
                    raise APIError(
                        "FORBIDDEN",
                        "Only administrators can create credentials.",
                        403,
                    )
                if self.chat_service is None:
                    raise APIError(
                        "CREDENTIAL_STORAGE_UNAVAILABLE",
                        "Credential storage is not configured.",
                        503,
                    )
                body = self._read_json(handler)
                role = body.get("role")
                subject = body.get("subject")
                ttl_seconds = body.get("ttl_seconds", 30 * 24 * 60 * 60)
                if role not in ("admin", "user"):
                    raise APIError(
                        "INVALID_CREDENTIAL_ROLE",
                        "Credential role must be 'admin' or 'user'.",
                        400,
                    )
                if not isinstance(subject, str) or not subject.strip():
                    raise APIError(
                        "INVALID_CREDENTIAL_SUBJECT",
                        "Credential subject must be a non-empty string.",
                        400,
                    )
                if (
                    isinstance(ttl_seconds, bool)
                    or not isinstance(ttl_seconds, int)
                    or not 300 <= ttl_seconds <= 365 * 24 * 60 * 60
                ):
                    raise APIError(
                        "INVALID_CREDENTIAL_TTL",
                        "Credential TTL must be between 300 and 31536000 seconds.",
                        400,
                    )
                token = secrets.token_urlsafe(32)
                credential_id = str(uuid4())
                expires_at = (
                    datetime.now(timezone.utc)
                    + timedelta(seconds=ttl_seconds)
                ).isoformat()
                credential = self.chat_service.store.create_api_credential(
                    credential_id,
                    hashlib.sha256(token.encode("utf-8")).hexdigest(),
                    role,
                    subject.strip(),
                    expires_at,
                )
                self._record_audit(
                    principal,
                    "api_credential_created",
                    credential_id,
                    {"role": role, "subject": subject.strip()},
                )
                self._send_json(
                    handler,
                    201,
                    {
                        **credential,
                        "token": token,
                    },
                )
            elif (
                handler.command == "POST"
                and path.startswith("/v1/auth/credentials/")
                and path.endswith("/rotate")
            ):
                if principal[0] != "admin":
                    raise APIError(
                        "FORBIDDEN",
                        "Only administrators can rotate credentials.",
                        403,
                    )
                if self.chat_service is None:
                    raise APIError(
                        "CREDENTIAL_STORAGE_UNAVAILABLE",
                        "Credential storage is not configured.",
                        503,
                    )
                credential_id = unquote(path.split("/")[4])
                old = self.chat_service.store.get_api_credential(
                    credential_id
                )
                if old is None or old["revoked_at"] is not None:
                    raise APIError(
                        "CREDENTIAL_NOT_FOUND",
                        "The credential was not found or is revoked.",
                        404,
                    )
                body = self._read_json(handler)
                ttl_seconds = body.get("ttl_seconds", 30 * 24 * 60 * 60)
                if (
                    isinstance(ttl_seconds, bool)
                    or not isinstance(ttl_seconds, int)
                    or not 300 <= ttl_seconds <= 365 * 24 * 60 * 60
                ):
                    raise APIError(
                        "INVALID_CREDENTIAL_TTL",
                        "Credential TTL must be between 300 and 31536000 seconds.",
                        400,
                    )
                token = secrets.token_urlsafe(32)
                new_id = str(uuid4())
                expires_at = (
                    datetime.now(timezone.utc)
                    + timedelta(seconds=ttl_seconds)
                ).isoformat()
                new_credential = self.chat_service.store.create_api_credential(
                    new_id,
                    hashlib.sha256(token.encode("utf-8")).hexdigest(),
                    old["role"],
                    old["subject"],
                    expires_at,
                )
                if not self.chat_service.store.revoke_api_credential(
                    credential_id
                ):
                    raise APIError(
                        "CREDENTIAL_NOT_FOUND",
                        "The credential was not found or is already revoked.",
                        404,
                    )
                self._record_audit(
                    principal,
                    "api_credential_rotated",
                    new_id,
                    {
                        "replaced_id": credential_id,
                        "role": old["role"],
                        "subject": old["subject"],
                    },
                )
                self._send_json(
                    handler,
                    201,
                    {
                        **new_credential,
                        "token": token,
                        "replaced_id": credential_id,
                    },
                )
            elif (
                handler.command == "DELETE"
                and path.startswith("/v1/auth/credentials/")
            ):
                if principal[0] != "admin":
                    if not self._discard_request_body(handler):
                        return
                    raise APIError(
                        "FORBIDDEN",
                        "Only administrators can revoke credentials.",
                        403,
                    )
                if self.chat_service is None:
                    raise APIError(
                        "CREDENTIAL_STORAGE_UNAVAILABLE",
                        "Credential storage is not configured.",
                        503,
                    )
                credential_id = unquote(path.split("/")[4])
                if not self.chat_service.store.revoke_api_credential(
                    credential_id
                ):
                    raise APIError(
                        "CREDENTIAL_NOT_FOUND",
                        "The credential was not found or is already revoked.",
                        404,
                    )
                self._record_audit(
                    principal,
                    "api_credential_revoked",
                    credential_id,
                    {},
                )
                self._send_json(
                    handler,
                    200,
                    {"revoked": True, "id": credential_id},
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
                self._record_audit(
                    principal,
                    "workflow_created",
                    workflow.get("id"),
                    {"name": workflow.get("name")},
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
                self._record_audit(
                    principal,
                    "workflow_run_created",
                    result.get("id"),
                    {"workflow_id": workflow_id},
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
                result = self.api.cancel_run(run_id)
                self._record_audit(
                    principal,
                    "workflow_run_cancelled",
                    run_id,
                    {},
                )
                self._send_json(
                    handler,
                    200,
                    result,
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
                self._record_audit(
                    principal,
                    "workflow_approval_decided",
                    run_id,
                    {
                        "node": node_name,
                        "approved": body["approved"],
                    },
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

    def handle_options(
        self,
        handler: BaseHTTPRequestHandler,
    ) -> None:
        origin = handler.headers.get("Origin")
        if not self._origin_allowed(handler):
            self._send_json(
                handler,
                403,
                {
                    "code": "ORIGIN_NOT_ALLOWED",
                    "message": "This request origin is not allowed.",
                },
            )
            return
        headers: dict[str, str] = {}
        if origin:
            headers["Access-Control-Allow-Origin"] = origin
            headers["Vary"] = "Origin"
        headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
        headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        headers["Access-Control-Max-Age"] = "600"
        handler.send_response(204)
        handler.send_header("Content-Length", "0")
        for name, value in headers.items():
            handler.send_header(name, value)
        handler.end_headers()

    def _origin_allowed(
        self,
        handler: BaseHTTPRequestHandler,
    ) -> bool:
        origin = handler.headers.get("Origin")
        if not origin:
            return True
        normalized = origin.rstrip("/")
        if normalized in self.allowed_origins:
            return True
        host = handler.headers.get("Host", "")
        try:
            origin_host = urlparse(normalized).netloc
        except ValueError:
            return False
        return bool(origin_host and origin_host == host)

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
        if self.chat_service is not None:
            token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
            credential = self.chat_service.store.authenticate_api_credential(
                token_hash
            )
            if credential is not None:
                return credential
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

    @staticmethod
    def _delegation_owner(principal: tuple[str, str]) -> str:
        return hashlib.sha256(
            f"delegation:{principal[0]}:{principal[1]}".encode("utf-8")
        ).hexdigest()

    def _record_audit(
        self,
        principal: tuple[str, str],
        action: str,
        resource_id: str | None,
        details: dict,
    ) -> None:
        if self.chat_service is None:
            return
        actor_id = hashlib.sha256(
            f"actor:{principal[0]}:{principal[1]}".encode("utf-8")
        ).hexdigest()
        self.chat_service.store.record_audit(
            actor_id,
            action,
            resource_id,
            details,
        )

    @staticmethod
    def _audit_query_integer(
        query: dict[str, list[str]],
        name: str,
        *,
        default: int,
        minimum: int,
        maximum: int,
    ) -> int:
        values = query.get(name)
        if values is None:
            return default
        if (
            len(values) != 1
            or not values[0].isascii()
            or not values[0].isdecimal()
        ):
            raise APIError(
                "INVALID_AUDIT_QUERY",
                f"{name} must be a single integer.",
                400,
            )
        value = int(values[0])
        if not minimum <= value <= maximum:
            raise APIError(
                "INVALID_AUDIT_QUERY",
                f"{name} must be between {minimum} and {maximum}.",
                400,
            )
        return value

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
        origin = handler.headers.get("Origin")
        if origin and self._origin_allowed(handler):
            handler.send_header(
                "Access-Control-Allow-Origin",
                origin,
            )
            handler.send_header("Vary", "Origin")
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

    def _send_export(
        self,
        handler: BaseHTTPRequestHandler,
        body: bytes,
        content_type: str,
        filename: str,
    ) -> None:
        handler.send_response(200)
        handler.send_header(
            "Content-Type",
            f"{content_type}; charset=utf-8",
        )
        handler.send_header("Cache-Control", "no-store")
        handler.send_header(
            "Content-Disposition",
            f'attachment; filename="{filename}"',
        )
        handler.send_header(
            "Content-Length",
            str(len(body)),
        )
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
            path in ("/chat", "/coding", "/chat/coding")
            or path.startswith("/coding/share/")
            or path.startswith("/chat/coding/share/")
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

    def _stream_activity_events(
        self,
        handler: BaseHTTPRequestHandler,
        owner_id: str,
        conversation_id: str,
        run_id: str | None,
    ) -> None:
        subscription_id = (
            self.event_bus.subscribe(run_id)
            if run_id
            else self.event_bus.subscribe(None)
        )
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream")
        handler.send_header("Cache-Control", "no-cache")
        handler.send_header("Connection", "close")
        handler.close_connection = True
        handler.end_headers()

        try:
            history = self.chat_service.store.list_activity_events(
                owner_id,
                conversation_id,
                run_id=run_id,
            )
            snapshot = json.dumps({
                "events": history,
            }).encode("utf-8")
            handler.wfile.write(
                b"event: activity.snapshot\n"
                b"data: " + snapshot + b"\n\n"
            )
            handler.wfile.flush()

            if run_id:
                terminal = any(
                    event["status"] in ("completed", "failed", "cancelled")
                    and event["event_type"].startswith("response.")
                    for event in history
                )
                if terminal:
                    return

            next_heartbeat = time.monotonic() + 15
            while True:
                events = self.event_bus.consume(subscription_id, limit=100)
                for event in events:
                    payload = event.to_dict()
                    activity = payload.get("payload", {})
                    if activity.get("conversation_id") != conversation_id:
                        continue
                    if run_id and activity.get("run_id") != run_id:
                        continue
                    if activity.get("visibility") != "user":
                        continue
                    handler.wfile.write(
                        (
                            f"event: {event.event_type}\n"
                            f"data: {json.dumps(payload)}\n\n"
                        ).encode("utf-8")
                    )
                    handler.wfile.flush()
                    if (
                        activity.get("status") in ("completed", "failed", "cancelled")
                        and activity.get("event_type") in (
                            "response.completed",
                            "response.failed",
                            "execution.completed",
                            "execution.failed",
                            "execution.cancelled",
                        )
                    ):
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
