import json
import os
from threading import Event
from pathlib import Path

from app.agents.coding_agent import CodingAgent
from app.agents.agent_registry import AgentRegistry
from app.agents.delegation_worker import DelegationWorker
from app.agents.coordinator import (
    CoordinatorAgent,
    DelegationPermissionPolicy,
)
from app.agents.shared_memory import SharedMemory
from app.api.http_server import WorkflowHTTPServer
from app.api.security_config import read_boolean_env, validate_api_auth
from app.api.workflow_service import WorkflowAPIService
from app.chat.service import ChatService
from app.chat.store import ChatStore
from app.chat.web_search import BraveWebSearch
from app.config.loader import Loader
from app.factories.provider_factory import ProviderFactory
from app.health.server import HealthServer
from app.realtime.event_bus import EventBus
from app.workflows.engine import WorkflowEngine
from app.workflows.models import Workflow, WorkflowNode
from app.workflows.persistence import WorkflowPersistenceStore
from app.runtime.unified_agent_runtime import UnifiedAgentRuntime
from app.research.providers import BraveSearchProvider, SearXNGProvider
from app.research.search_manager import SearchManager


class ChatDelegationAgent:
    def __init__(self, chat_service: ChatService):
        self.chat_service = chat_service

    def chat(self, prompt: str) -> str:
        conversation = self.chat_service.create_conversation("delegation:chat")
        result = self.chat_service.send_message(
            "delegation:chat",
            conversation["id"],
            prompt,
            f"delegation-{conversation['id']}",
            mode="chat",
        )
        return result["assistant_message"]["content"]


class CodingDelegationAgent:
    def __init__(self, coding_agent: CodingAgent):
        self.coding_agent = coding_agent

    def chat(self, prompt: str) -> str:
        proposal = self.coding_agent.propose(
            prompt,
            [],
            owner_id="delegation",
            actor_id="delegation",
        )
        return json.dumps(
            {
                "proposal_id": proposal.get("id"),
                "summary": proposal.get("proposal"),
                "status": proposal.get("status"),
            },
            sort_keys=True,
        )


def create_demo_api(
    persistence_store: WorkflowPersistenceStore | None = None,
) -> tuple[WorkflowAPIService, EventBus]:
    bus = EventBus()
    engine = WorkflowEngine(event_bus=bus)
    api = WorkflowAPIService(engine, persistence_store)

    demo = Workflow(name="Demo Approval Workflow")
    demo.add_node(
        WorkflowNode(
            name="prepare",
            action=lambda context, dependencies: "Prepared",
        )
    )
    demo.add_node(
        WorkflowNode(
            name="review",
            dependencies=["prepare"],
            action=lambda context, dependencies:
                f"{dependencies['prepare']} and reviewed",
            requires_approval=True,
        )
    )
    api.register_workflow(demo)
    return api, bus


def main() -> None:
    settings = Loader().load()
    role_tokens = {}
    admin_token = os.getenv("AI_AGENT_ADMIN_TOKEN")
    user_token = os.getenv("AI_AGENT_USER_TOKEN")
    if admin_token and admin_token.strip():
        role_tokens[admin_token] = "admin"
    if user_token and user_token.strip():
        role_tokens[user_token] = "user"
    user_tokens_json = os.getenv("AI_AGENT_USER_TOKENS", "")
    if user_tokens_json:
        try:
            user_tokens = json.loads(user_tokens_json)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "AI_AGENT_USER_TOKENS must be a JSON object of tokens to subjects."
            ) from exc
        if not isinstance(user_tokens, dict):
            raise ValueError(
                "AI_AGENT_USER_TOKENS must be a JSON object of tokens to subjects."
            )
        for token, subject in user_tokens.items():
            if (
                not isinstance(token, str)
                or not token.strip()
                or not isinstance(subject, str)
                or not subject.strip()
            ):
                raise ValueError(
                    "AI_AGENT_USER_TOKENS keys and subjects must be non-empty strings."
                )
            role_tokens[token] = ("user", subject.strip())

    api_host = os.getenv("AI_AGENT_API_HOST", "127.0.0.1")
    api_token = os.getenv("AI_AGENT_API_TOKEN") or None
    if api_token is not None and not api_token.strip():
        api_token = None
    require_auth = read_boolean_env(
        "AI_AGENT_REQUIRE_AUTH",
        default=False,
    )
    validate_api_auth(
        api_host,
        require_auth=require_auth,
        has_configured_token=bool(api_token or role_tokens),
    )

    provider = ProviderFactory(settings).create()
    database_path = os.getenv(
        "AI_AGENT_CHAT_DATABASE",
        str(Path("data") / "chat.sqlite3"),
    )
    retention_value = os.getenv("AI_AGENT_CODING_AUDIT_RETENTION_DAYS", "365")
    try:
        coding_audit_retention_days = int(retention_value)
    except ValueError as exc:
        raise ValueError(
            "AI_AGENT_CODING_AUDIT_RETENTION_DAYS must be a non-negative integer."
        ) from exc
    audit_retention_value = os.getenv(
        "AI_AGENT_AUDIT_RETENTION_DAYS",
        "365",
    )
    try:
        audit_retention_days = int(audit_retention_value)
    except ValueError as exc:
        raise ValueError(
            "AI_AGENT_AUDIT_RETENTION_DAYS must be a non-negative integer."
        ) from exc
    store = ChatStore(
        database_path,
        coding_audit_retention_days=coding_audit_retention_days,
        audit_retention_days=audit_retention_days,
    )
    store.prune_coding_audit()
    store.prune_audit()
    credential_retention_value = os.getenv(
        "AI_AGENT_CREDENTIAL_RETENTION_DAYS",
        "30",
    )
    try:
        credential_retention_days = int(credential_retention_value)
    except ValueError as exc:
        raise ValueError(
            "AI_AGENT_CREDENTIAL_RETENTION_DAYS must be a non-negative integer."
        ) from exc
    rate_hit_retention_value = os.getenv(
        "AI_AGENT_RATE_LIMIT_HIT_RETENTION_SECONDS",
        "86400",
    )
    try:
        rate_hit_retention_seconds = int(rate_hit_retention_value)
    except ValueError as exc:
        raise ValueError(
            "AI_AGENT_RATE_LIMIT_HIT_RETENTION_SECONDS must be a non-negative integer."
        ) from exc
    store.prune_api_credentials(credential_retention_days)
    store.prune_api_rate_limit_hits(rate_hit_retention_seconds)
    api, bus = create_demo_api(store)
    agent_runtime = UnifiedAgentRuntime(provider)
    brave_search = BraveSearchProvider(
        os.getenv("AI_AGENT_BRAVE_SEARCH_API_KEY")
        or os.getenv("BRAVE_SEARCH_API_KEY"),
    )
    searxng_search = SearXNGProvider(
        os.getenv("SEARXNG_BASE_URL"),
        enabled=os.getenv("SEARXNG_ENABLED", "false").lower() in ("1", "true", "yes"),
        timeout=float(os.getenv("SEARXNG_TIMEOUT", "15")),
        categories=os.getenv("SEARXNG_DEFAULT_CATEGORIES", "general"),
    )
    search_manager = SearchManager(
        brave_search,
        searxng_search,
        mode=os.getenv("SEARCH_PROVIDER", "auto").lower(),
        fallback_enabled=os.getenv("SEARCH_FALLBACK_ENABLED", "true").lower()
        in ("1", "true", "yes"),
    )
    chat_service = ChatService(
        store,
        provider,
        web_search_provider=BraveWebSearch(
            os.getenv("AI_AGENT_BRAVE_SEARCH_API_KEY")
        ),
        event_bus=bus,
        agent_runtime=agent_runtime,
        search_manager=search_manager,
    )
    coding_workspace = os.getenv("AI_AGENT_CODING_WORKSPACE")
    coding_agent = (
        CodingAgent(
            provider,
            coding_workspace,
            generation_timeout=int(
                os.getenv("AI_AGENT_CODING_TIMEOUT", "180")
            ),
            persistence_store=store,
        )
        if coding_workspace
        else None
    )
    delegation_registry = AgentRegistry()
    delegation_registry.register(
        "chat",
        ChatDelegationAgent(chat_service),
    )
    if coding_agent is not None:
        delegation_registry.register(
            "coding",
            CodingDelegationAgent(coding_agent),
        )
    delegation_policy = DelegationPermissionPolicy({
        "admin": None,
        "user": tuple(
            name for name in ("chat", "coding")
            if delegation_registry.get(name) is not None
        ),
    })
    delegation_coordinator = CoordinatorAgent(
        delegation_registry,
        SharedMemory(),
        "chat",
    )
    delegation_worker = DelegationWorker(
        delegation_coordinator,
        store,
    )
    delegation_worker.start()
    allowed_origins = tuple(
        origin.strip()
        for origin in os.getenv(
            "AI_AGENT_ALLOWED_ORIGINS",
            "",
        ).split(",")
        if origin.strip()
    )

    server = WorkflowHTTPServer(
        api,
        bus,
        host=api_host,
        port=int(os.getenv("AI_AGENT_API_PORT", "8081")),
        api_token=api_token,
        role_tokens=role_tokens,
        chat_service=chat_service,
        coding_agent=coding_agent,
        secure_guest_cookies=read_boolean_env(
            "AI_AGENT_COOKIE_SECURE",
            default=False,
        ),
        require_auth=require_auth,
        allowed_origins=allowed_origins,
        delegation_coordinator=delegation_coordinator,
        delegation_policy=delegation_policy,
    )
    health_server = HealthServer(
        host=os.getenv("AI_AGENT_HOST", "0.0.0.0"),
        port=int(os.getenv("AI_AGENT_PORT", "8080")),
        readiness_checks={
            "database": store.health_check,
            provider.provider_name: provider.health_check,
        },
    )

    server.start()
    health_server.start()
    stopped = Event()
    try:
        import signal

        for signal_name in ("SIGTERM", "SIGINT"):
            if hasattr(signal, signal_name):
                signal.signal(
                    getattr(signal, signal_name),
                    lambda *_args: stopped.set(),
                )
        stopped.wait()
    except KeyboardInterrupt:
        stopped.set()
    finally:
        delegation_worker.stop()
        server.stop()
        health_server.stop()
        chat_service.close()


if __name__ == "__main__":
    main()
