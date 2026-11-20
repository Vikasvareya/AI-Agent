import json
import os
from threading import Event
from pathlib import Path

from app.agents.coding_agent import CodingAgent
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
    store = ChatStore(database_path)
    api, bus = create_demo_api(store)
    chat_service = ChatService(
        store,
        provider,
        web_search_provider=BraveWebSearch(
            os.getenv("AI_AGENT_BRAVE_SEARCH_API_KEY")
        ),
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
    )
    health_server = HealthServer(
        host=os.getenv("AI_AGENT_HOST", "0.0.0.0"),
        port=int(os.getenv("AI_AGENT_PORT", "8080")),
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
        server.stop()
        health_server.stop()
        chat_service.close()


if __name__ == "__main__":
    main()
