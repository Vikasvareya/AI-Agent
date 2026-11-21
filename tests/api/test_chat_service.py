import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from app.chat.service import ChatError, ChatService
from app.chat.store import ChatStore
from app.chat.web_search import BraveWebSearch, WebSearchError
from app.realtime.event_bus import EventBus
from app.runtime.unified_agent_runtime import UnifiedAgentRuntime


class FakeProvider:
    def __init__(self):
        self.prompts = []
        self.selected_models = []
        self.refresh_requests = []
        self.response = "Hello from the assistant."

    @property
    def default_model(self):
        return "fake-chat"

    @property
    def provider_name(self):
        return "fake"

    def list_models(self, *, refresh=False):
        self.refresh_requests.append(refresh)
        return [
            {"id": "fake-chat", "name": "Fake Chat", "provider": "fake"},
            {"id": "fake-code", "name": "Fake Code", "provider": "fake"},
        ]

    def ask(self, messages, *, model=None, timeout=None):
        self.prompts.append(messages)
        self.selected_models.append(model)
        return self.response


def _service(tmp_path):
    provider = FakeProvider()
    service = ChatService(
        ChatStore(tmp_path / "chat.sqlite3"),
        provider,
        agent_runtime=UnifiedAgentRuntime(provider),
    )
    return service, provider


def test_chat_persists_conversations_and_keeps_history(tmp_path):
    service, provider = _service(tmp_path)
    conversation = service.create_conversation("owner-a")

    first = service.send_message(
        "owner-a",
        conversation["id"],
        "Hello",
        "message-1",
    )
    provider.response = "I remember your greeting."
    second = service.send_message(
        "owner-a",
        conversation["id"],
        "What did I say?",
        "message-2",
    )

    assert first["assistant_message"]["content"] == "Hello from the assistant."
    assert second["assistant_message"]["content"] == "I remember your greeting."
    assert [message["role"] for message in provider.prompts[1]] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
    assert len(service.get_conversation("owner-a", conversation["id"])["messages"]) == 4


def test_chat_store_survives_reopen(tmp_path):
    database_path = tmp_path / "chat.sqlite3"
    first_store = ChatStore(database_path)
    conversation = first_store.create_conversation("owner-a", "Saved chat")
    first_store.close()

    reopened_store = ChatStore(database_path)
    try:
        restored = reopened_store.get_conversation(
            "owner-a",
            conversation["id"],
        )
        assert restored is not None
        assert restored["title"] == "Saved chat"
    finally:
        reopened_store.close()


def test_chat_store_health_check_reports_database_availability(
    tmp_path,
    monkeypatch,
):
    store = ChatStore(tmp_path / "chat.sqlite3")
    try:
        assert store.health_check() is True

        def unavailable_database(*_args, **_kwargs):
            raise sqlite3.OperationalError("database unavailable")

        monkeypatch.setattr("app.chat.store.sqlite3.connect", unavailable_database)
        assert store.health_check() is False
    finally:
        store.close()


@pytest.mark.parametrize(
    ("retention_days", "expected_pruned", "expected_events"),
    ((30, 1, 0), (0, 0, 1)),
)
def test_chat_store_applies_coding_audit_retention(
    tmp_path,
    retention_days,
    expected_pruned,
    expected_events,
):
    store = ChatStore(
        tmp_path / "chat.sqlite3",
        coding_audit_retention_days=retention_days,
    )
    try:
        store.save_coding_permission_mode(
            "manual",
            "manual",
            "a" * 64,
        )
        old_timestamp = (
            datetime.now(timezone.utc) - timedelta(days=31)
        ).isoformat()
        with store._connection() as connection:
            store._execute(
                connection,
                "UPDATE coding_audit SET created_at = ?",
                (old_timestamp,),
            )

        assert store.prune_coding_audit() == expected_pruned
        assert len(store.list_coding_audit()) == expected_events
    finally:
        store.close()


@pytest.mark.parametrize(
    ("retention_days", "expected_pruned", "expected_events"),
    ((30, 1, 0), (0, 0, 1)),
)
def test_chat_store_applies_general_audit_retention(
    tmp_path,
    retention_days,
    expected_pruned,
    expected_events,
):
    store = ChatStore(
        tmp_path / "chat.sqlite3",
        audit_retention_days=retention_days,
    )
    try:
        store.record_audit("a" * 64, "workflow_created", "wf-1", {})
        old_timestamp = (
            datetime.now(timezone.utc) - timedelta(days=31)
        ).isoformat()
        with store._connection() as connection:
            store._execute(
                connection,
                "UPDATE audit_events SET created_at = ?",
                (old_timestamp,),
            )

        assert store.prune_audit() == expected_pruned
        assert len(store.list_audit()) == expected_events
    finally:
        store.close()


def test_chat_store_distributed_rate_limit_is_shared(tmp_path):
    store = ChatStore(tmp_path / "ratelimit.sqlite3")
    try:
        assert store.allow_distributed_request("203.0.113.10", 2, 60) is True
        assert store.allow_distributed_request("203.0.113.10", 2, 60) is True
        assert store.allow_distributed_request("203.0.113.10", 2, 60) is False
        assert store.allow_distributed_request("203.0.113.11", 2, 60) is True
    finally:
        store.close()


def test_chat_store_prunes_expired_credentials_and_old_rate_hits(tmp_path):
    store = ChatStore(tmp_path / "cleanup.sqlite3")
    try:
        store.create_api_credential(
            "old-expired",
            "a" * 64,
            "user",
            "old-user",
            (datetime.now(timezone.utc) - timedelta(days=31)).isoformat(),
        )
        store.create_api_credential(
            "active",
            "b" * 64,
            "admin",
            "active-admin",
            (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        )
        assert store.prune_api_credentials(30) == 1
        assert store.get_api_credential("old-expired") is None
        assert store.get_api_credential("active") is not None

        assert store.allow_distributed_request("203.0.113.20", 100, 60) is True
        old_timestamp = (
            datetime.now(timezone.utc) - timedelta(hours=25)
        ).isoformat()
        with store._connection() as connection:
            store._execute(
                connection,
                "UPDATE api_rate_limit_hits SET occurred_at = ?",
                (old_timestamp,),
            )
        assert store.prune_api_rate_limit_hits(86_400) == 1
    finally:
        store.close()


@pytest.mark.parametrize("retention_days", (-1, 36_501))
def test_chat_store_rejects_invalid_coding_audit_retention(
    tmp_path,
    retention_days,
):
    with pytest.raises(ValueError, match="between 0 and 36500"):
        ChatStore(
            tmp_path / "chat.sqlite3",
            coding_audit_retention_days=retention_days,
        )


def test_coding_sessions_persist_context_and_revoke_shared_links(tmp_path):
    database_path = tmp_path / "chat.sqlite3"
    store = ChatStore(database_path)
    session = store.create_coding_session("owner-a", "project-a", "Feature work")
    store.append_coding_session_message(
        "owner-a",
        session["id"],
        "user",
        "Add a new route.",
    )
    store.append_coding_session_message(
        "owner-a",
        session["id"],
        "assistant",
        "Proposal summary.",
    )
    expires_at = "2999-01-01T00:00:00+00:00"
    assert store.create_coding_session_share(
        "owner-a",
        session["id"],
        "unguessable-share-token",
        expires_at,
    )
    store.close()

    reopened_store = ChatStore(database_path)
    try:
        restored = reopened_store.get_coding_session("owner-a", session["id"])
        shared = reopened_store.get_shared_coding_session("unguessable-share-token")
        assert restored is not None
        assert restored["project_id"] == "project-a"
        assert [message["role"] for message in restored["messages"]] == [
            "user",
            "assistant",
        ]
        assert shared is not None
        assert shared["title"] == "Feature work"
        assert reopened_store.revoke_coding_session_shares(
            "owner-a",
            session["id"],
        ) == 1
        assert reopened_store.get_shared_coding_session(
            "unguessable-share-token",
        ) is None
    finally:
        reopened_store.close()


def test_chat_isolates_owners_and_replays_idempotent_messages(tmp_path):
    service, provider = _service(tmp_path)
    conversation = service.create_conversation("owner-a")
    result = service.send_message(
        "owner-a",
        conversation["id"],
        "Hello",
        "message-1",
    )

    replay = service.send_message(
        "owner-a",
        conversation["id"],
        "Hello",
        "message-1",
    )
    assert replay["replayed"] is True
    assert replay["model"] == result["model"]
    assert replay["mode"] == result["mode"]
    assert replay["assistant_message"]["id"] == result["assistant_message"]["id"]
    assert len(provider.prompts) == 1

    with pytest.raises(ChatError) as error:
        service.get_conversation("owner-b", conversation["id"])
    assert error.value.status_code == 404

    with pytest.raises(ChatError) as error:
        service.send_message(
            "owner-a",
            conversation["id"],
            "Different text",
            "message-1",
        )
    assert error.value.code == "IDEMPOTENCY_CONFLICT"


def test_chat_provider_failure_is_reported_and_retryable(tmp_path):
    service, provider = _service(tmp_path)
    conversation = service.create_conversation("owner-a")

    def fail(_messages, *, model=None):
        raise RuntimeError("provider unavailable")

    provider.ask = fail
    with pytest.raises(ChatError) as error:
        service.send_message(
            "owner-a",
            conversation["id"],
            "Hello",
            "message-1",
        )
    assert error.value.code == "MODEL_UNAVAILABLE"
    assert "conversation and saved profile remain available" in error.value.message
    assert "Reference:" in error.value.message

    provider.ask = lambda _messages, *, model=None: "Recovered."
    retried = service.send_message(
        "owner-a",
        conversation["id"],
        "Hello",
        "message-1",
    )
    assert retried["assistant_message"]["content"] == "Recovered."


def test_chat_rejects_empty_and_oversized_messages(tmp_path):
    service, _ = _service(tmp_path)
    conversation = service.create_conversation("owner-a")

    with pytest.raises(ChatError) as error:
        service.send_message(
            "owner-a",
            conversation["id"],
            "  ",
            "message-1",
        )
    assert error.value.code == "INVALID_MESSAGE"

    with pytest.raises(ChatError) as error:
        service.send_message(
            "owner-a",
            conversation["id"],
            "x" * 8001,
            "message-2",
        )
    assert error.value.status_code == 413


def test_chat_lists_models_and_switches_to_coding_mode(tmp_path):
    service, provider = _service(tmp_path)
    conversation = service.create_conversation("owner-a")

    catalog = service.list_models()
    refreshed_catalog = service.list_models(refresh=True)
    assert catalog["provider"] == "fake"
    assert refreshed_catalog["models"] == catalog["models"]
    assert provider.refresh_requests == [False, True]
    assert [model["id"] for model in catalog["models"]] == [
        "fake-chat",
        "fake-code",
    ]

    result = service.send_message(
        "owner-a",
        conversation["id"],
        "Review this function",
        "message-code",
        model="fake-code",
        mode="coding",
    )
    assert result["model"] == "fake-code"
    assert result["mode"] == "coding"
    assert provider.selected_models == ["fake-code"]
    assert "coding assistant" in provider.prompts[0][0]["content"].lower()


def test_chat_rejects_model_not_in_provider_catalog(tmp_path):
    service, provider = _service(tmp_path)
    conversation = service.create_conversation("owner-a")

    with pytest.raises(ChatError) as error:
        service.send_message(
            "owner-a",
            conversation["id"],
            "Hello",
            "unknown-model",
            model="not-installed",
        )

    assert error.value.code == "MODEL_NOT_FOUND"
    assert provider.prompts == []


@pytest.mark.parametrize("mode", ["image", "video"])
def test_chat_rejects_unconfigured_generation_modes(tmp_path, mode):
    service, _ = _service(tmp_path)
    conversation = service.create_conversation("owner-a")

    with pytest.raises(ChatError) as error:
        service.send_message(
            "owner-a",
            conversation["id"],
            "Create something",
            f"message-{mode}",
            mode=mode,
        )
    assert error.value.code == "CAPABILITY_UNAVAILABLE"
    assert error.value.status_code == 501


def test_chat_capabilities_report_media_provider_requirements(tmp_path):
    service, _ = _service(tmp_path)
    capabilities = {
        item["id"]: item
        for item in service.capabilities()["modes"]
    }

    assert capabilities["chat"]["available"] is True
    assert capabilities["coding"]["available"] is True
    assert capabilities["image"]["available"] is False
    assert "provider" in capabilities["image"]["reason"]
    assert capabilities["video"]["available"] is False
    assert "provider" in capabilities["video"]["reason"]
    assert capabilities["web_search"]["available"] is False
    service.close()


def test_freshness_sensitive_query_detected_without_checkbox(tmp_path):
    service, provider = _service(tmp_path)
    conversation = service.create_conversation("owner-a")

    result = service.send_message(
        "owner-a",
        conversation["id"],
        "What is the current Laravel version?",
        "freshness-message",
    )

    assert "cannot reliably verify" in result["assistant_message"]["content"].lower()
    assert provider.prompts == []


def test_static_question_does_not_trigger_automatic_research(tmp_path):
    service, provider = _service(tmp_path)
    conversation = service.create_conversation("owner-a")

    result = service.send_message(
        "owner-a",
        conversation["id"],
        "Explain dependency injection.",
        "static-message",
    )

    assert result["assistant_message"]["content"] == "Hello from the assistant."
    assert len(provider.prompts) == 1


def test_chat_web_search_is_opt_in_and_returns_cited_sources(tmp_path):
    class FakeSearch:
        available = True

        def __init__(self):
            self.queries = []

        def search(self, query):
            self.queries.append(query)
            return [{
                "title": "Python documentation",
                "url": "https://docs.python.org/",
                "description": "Official Python documentation.",
            }]

    provider = FakeProvider()
    search = FakeSearch()
    service = ChatService(
        ChatStore(tmp_path / "chat.sqlite3"),
        provider,
        web_search_provider=search,
    )
    conversation = service.create_conversation("owner-a")

    result = service.send_message(
        "owner-a",
        conversation["id"],
        "Where is the Python documentation?",
        "search-message",
        search_query="official Python documentation",
        web_search=True,
    )

    assert search.queries == ["official Python documentation"]
    assert result["web_search"] is True
    assert result["sources"][0]["url"] == "https://docs.python.org/"
    assert "[1]" in result["assistant_message"]["content"]
    assert "https://docs.python.org/" in result["assistant_message"]["content"]
    assert "untrusted data" in provider.prompts[0][0]["content"]
    assert "Official Python documentation" in provider.prompts[0][-1]["content"]


def test_chat_web_search_requires_configuration_before_storing_message(tmp_path):
    service, _ = _service(tmp_path)
    conversation = service.create_conversation("owner-a")

    with pytest.raises(ChatError) as error:
        service.send_message(
            "owner-a",
            conversation["id"],
            "Search for this",
            "search-message",
            web_search=True,
        )

    assert error.value.code == "WEB_SEARCH_UNAVAILABLE"
    assert service.get_conversation("owner-a", conversation["id"])["messages"] == []


def test_brave_search_returns_sources_and_blocks_common_secrets(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _limit):
            return (
                b'{"web":{"results":[{"title":"Docs",'
                b'"url":"https://example.com/docs",'
                b'"description":"Official docs."}]}}'
            )

    calls = []

    def fake_urlopen(request, *, timeout):
        calls.append((request, timeout))
        return FakeResponse()

    monkeypatch.setattr("app.chat.web_search.urlopen", fake_urlopen)
    search = BraveWebSearch("configured-secret")
    results = search.search("official documentation")

    assert results == [{
        "title": "Docs",
        "url": "https://example.com/docs",
        "description": "Official docs.",
    }]
    assert calls[0][0].get_header("X-subscription-token") == "configured-secret"
    assert calls[0][1] == 10

    with pytest.raises(WebSearchError, match="credentials and source code"):
        search.search("api_key=private-value")
    assert len(calls) == 1


def test_unknown_person_query_never_generates_unverified_profile(tmp_path):
    service, provider = _service(tmp_path)
    conversation = service.create_conversation("owner-a")

    result = service.send_message(
        "owner-a",
        conversation["id"],
        "Who is Vikas?",
        "unknown-person-1",
    )

    assert "don't have enough verified information" in result["assistant_message"]["content"]
    assert "New Delhi" not in result["assistant_message"]["content"]
    assert provider.prompts == []


def test_confirmed_profile_supports_resume_across_conversations(tmp_path):
    service, provider = _service(tmp_path)
    first = service.create_conversation("owner-a")
    service.send_message(
        "owner-a",
        first["id"],
        "I work as a software engineer.",
        "casual-profession",
    )
    confirmed = service.send_message(
        "owner-a",
        first["id"],
        "Yes, remember it.",
        "confirm-profession",
    )
    assert "Confirmed and saved" in confirmed["assistant_message"]["content"]

    second = service.create_conversation("owner-a")
    resume = service.send_message(
        "owner-a",
        second["id"],
        "Create an ATS-friendly resume with it.",
        "resume-request",
    )

    assert "ATS-friendly resume draft" in resume["assistant_message"]["content"]
    assert "software engineer" in resume["assistant_message"]["content"].lower()
    assert "[Name not provided]" in resume["assistant_message"]["content"]
    assert "[Employment history not provided]" in resume["assistant_message"]["content"]
    assert provider.prompts == []


def test_resume_without_confirmed_profile_is_honest(tmp_path):
    service, provider = _service(tmp_path)
    conversation = service.create_conversation("owner-a")

    result = service.send_message(
        "owner-a",
        conversation["id"],
        "Create a resume.",
        "resume-empty",
    )

    assert "don't have any confirmed profile information" in result["assistant_message"]["content"]
    assert provider.prompts == []


def test_explicit_memory_is_saved_and_retrieved_across_conversations(tmp_path):
    service, provider = _service(tmp_path)
    first = service.create_conversation("owner-a")
    saved = service.send_message(
        "owner-a",
        first["id"],
        "Remember that I am a software engineer.",
        "memory-explicit-1",
    )

    assert "saved to your profile" in saved["assistant_message"]["content"].lower()
    assert saved["memory_record"]["category"] == "professional"
    assert saved["memory_record"]["value"] == "software engineer"

    second = service.create_conversation("owner-a")
    result = service.send_message(
        "owner-a",
        second["id"],
        "What is my profession?",
        "memory-retrieve-1",
    )
    assert len(service.memory_service.retrieve_relevant(
        "owner-a",
        "What is my profession?",
    )) == 1
    assert result["assistant_message"]["content"]
    assert service.store.list_memory_records("owner-b") == []


def test_casual_memory_requires_confirmation_and_sensitive_memory_is_rejected(tmp_path):
    service, _ = _service(tmp_path)
    conversation = service.create_conversation("owner-a")

    proposed = service.send_message(
        "owner-a",
        conversation["id"],
        "I work as a software engineer.",
        "memory-casual-1",
    )
    assert "Would you like me to remember" in proposed["assistant_message"]["content"]
    assert proposed["memory_record"]["status"] == "pending_confirmation"

    sensitive = service.send_message(
        "owner-a",
        conversation["id"],
        "Remember that my password is hunter2.",
        "memory-sensitive-1",
    )
    assert "cannot store" in sensitive["assistant_message"]["content"].lower()
    assert all(
        "password" not in record["value"].lower()
        for record in service.store.list_memory_records("owner-a")
    )


def test_profile_correction_requires_confirmation_and_records_history(tmp_path):
    service, _ = _service(tmp_path)
    conversation = service.create_conversation("owner-a")
    record = service.store.save_memory_record(
        "owner-a",
        conversation_id=conversation["id"],
        category="identity",
        key="location",
        value="New Delhi",
        source="explicit_user_statement",
        confidence=1.0,
        status="confirmed",
    )

    proposed = service.send_message(
        "owner-a",
        conversation["id"],
        "I live in Jaipur.",
        "correction-propose",
    )
    assert "profile correction" in proposed["assistant_message"]["content"].lower()
    assert proposed["memory_correction"]["proposed_value"] == "Jaipur"

    confirmed = service.send_message(
        "owner-a",
        conversation["id"],
        "Yes, remember it.",
        "correction-confirm",
    )
    assert "confirmed and saved" in confirmed["assistant_message"]["content"].lower()
    updated = service.store.get_memory_record("owner-a", record["id"])
    assert updated["value"] == "Jaipur"
    history = service.store.list_memory_history("owner-a", record["id"])
    assert history[0]["previous_value"] == "New Delhi"
    assert history[0]["new_value"] == "Jaipur"


def test_resume_draft_can_be_edited_exported_and_deleted(tmp_path):
    service, _ = _service(tmp_path)
    draft = service.store.save_resume_draft(
        "owner-a",
        title="Professional Resume",
        content="Software Engineer",
    )

    edited = service.store.save_resume_draft(
        "owner-a",
        draft_id=draft["id"],
        title=draft["title"],
        content="Senior Software Engineer",
        status="edited",
    )
    assert edited["content"] == "Senior Software Engineer"
    assert edited["status"] == "edited"
    assert service.store.get_resume_draft("owner-b", draft["id"]) is None
    export = service.store.get_resume_draft("owner-a", draft["id"])
    assert export["content"] == "Senior Software Engineer"
    assert service.store.delete_resume_draft("owner-a", draft["id"]) is True


def test_memory_update_delete_and_clear_are_owner_scoped(tmp_path):
    service, _ = _service(tmp_path)
    record = service.store.save_memory_record(
        "owner-a",
        conversation_id=None,
        category="skills",
        key="skills",
        value="Laravel",
        source="explicit_user_statement",
        confidence=1.0,
        status="confirmed",
    )

    updated = service.store.update_memory_record(
        "owner-a",
        record["id"],
        value="Laravel and Python",
        status="confirmed",
    )
    assert updated["value"] == "Laravel and Python"
    assert service.store.get_memory_record("owner-b", record["id"]) is None
    assert service.store.delete_memory_record("owner-b", record["id"]) is False
    assert service.store.delete_memory_record("owner-a", record["id"]) is True
    assert service.store.clear_memory_records("owner-b") == 0


def test_browser_chat_route_style_executes_time_tool_without_provider_call(tmp_path):
    service, provider = _service(tmp_path)
    conversation = service.create_conversation("owner-a")

    result = service.send_message(
        "owner-a",
        conversation["id"],
        "What is the date today?",
        "date-message",
        mode="chat",
    )

    assert "202" in result["assistant_message"]["content"]
    assert provider.prompts == []


def test_browser_chat_route_style_executes_math_tool_without_provider_call(tmp_path):
    service, provider = _service(tmp_path)
    conversation = service.create_conversation("owner-a")

    result = service.send_message(
        "owner-a",
        conversation["id"],
        "25 * 4",
        "math-message",
        mode="chat",
    )

    assert result["assistant_message"]["content"] == "100"
    assert provider.prompts == []


def test_chat_activity_events_are_persisted_ordered_and_owner_scoped(tmp_path):
    provider = FakeProvider()
    bus = EventBus()
    store = ChatStore(tmp_path / "activity.sqlite3")
    service = ChatService(store, provider, event_bus=bus)
    conversation = service.create_conversation("owner-a")

    result = service.send_message(
        "owner-a",
        conversation["id"],
        "Hello",
        "activity-message",
        run_id="chat-run-1",
    )

    events = store.list_activity_events(
        "owner-a",
        conversation["id"],
        run_id="chat-run-1",
    )
    assert result["run_id"] == "chat-run-1"
    assert [event["sequence_number"] for event in events] == list(
        range(1, len(events) + 1)
    )
    assert events[0]["event_type"] == "request.received"
    assert events[-1]["event_type"] == "execution.completed"
    assert store.list_activity_events(
        "owner-b",
        conversation["id"],
        run_id="chat-run-1",
    ) == []


def test_chat_activity_event_deduplicates_duplicate_event_id(tmp_path):
    store = ChatStore(tmp_path / "dedupe.sqlite3")
    conversation = store.create_conversation("owner-a")
    event = {
        "event_id": "duplicate-event",
        "run_id": "run-1",
        "conversation_id": conversation["id"],
        "task_id": None,
        "agent_id": "chat_agent",
        "parent_task_id": None,
        "event_type": "request.received",
        "status": "completed",
        "summary": "Received your request.",
        "timestamp": "2026-11-21T00:00:00+00:00",
        "visibility": "user",
        "metadata": {},
    }

    first = store.record_activity_event("owner-a", event)
    second = store.record_activity_event("owner-a", event)

    assert first["sequence_number"] == 1
    assert second["sequence_number"] == 1
    assert len(store.list_activity_events(
        "owner-a",
        conversation["id"],
        run_id="run-1",
    )) == 1
