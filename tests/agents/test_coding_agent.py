import hashlib

import pytest

from app.agents.coding_agent import CodingAgent, CodingAgentError
from app.chat.store import ChatStore


class FakeProvider:
    default_model = "fake-default"
    provider_name = "fake"

    def __init__(self):
        self.messages = None
        self.selected_model = None
        self.requests = []
        self.responses = [
            (
                "Summary\n```diff\n"
                "--- a/src/app.py\n"
                "+++ b/src/app.py\n"
                "@@ -1,2 +1,2 @@\n"
                " def greet():\n"
                "-    return 'not the selected source'\n"
                "+    return 'hello'\n"
                "```"
            ),
            (
                "Summary\n```diff\n"
                "diff --git a/src/app.py b/src/app.py\n"
                "--- a/src/app.py\n"
                "+++ b/src/app.py\n"
                "@@ -1,2 +1,2 @@\n"
                " def greet():\n"
                "-    return 'hello'\n"
                "+    return 'Hello'\n"
                "```"
            ),
        ]

    def list_models(self, *, refresh=False):
        return [{"id": "fake-code"}]

    def ask(self, messages, *, model=None, timeout=None):
        self.messages = messages
        self.requests.append(messages)
        self.selected_model = model
        self.timeout = timeout
        return self.responses.pop(0)


def test_coding_agent_proposes_patch_from_selected_workspace_files(tmp_path):
    workspace = tmp_path / "workspace"
    (workspace / "src").mkdir(parents=True)
    source_file = workspace / "src" / "app.py"
    source_file.write_text("def greet():\n    return 'hello'\n", encoding="utf-8")
    (workspace / ".env").write_text("API_KEY=not-for-the-agent", encoding="utf-8")
    secret_directory = workspace / "secrets"
    secret_directory.mkdir()
    (secret_directory / "settings.py").write_text(
        "TOKEN = 'not-for-the-agent'",
        encoding="utf-8",
    )
    (workspace / "node_modules").mkdir()
    (workspace / "node_modules" / "package.js").write_text(
        "not source context",
        encoding="utf-8",
    )
    provider = FakeProvider()
    agent = CodingAgent(provider, workspace)

    assert agent.list_files()["files"] == ["src/app.py"]
    result = agent.propose(
        "Add a greeting argument.",
        ["src/app.py"],
        model="fake-code",
    )

    assert result["proposal"].startswith("Summary")
    assert result["files"] == ["src/app.py"]
    assert result["model"] == "fake-code"
    assert result["applied"] is False
    assert provider.selected_model == "fake-code"
    assert provider.timeout == 180
    prompt = "\n".join(
        message["content"]
        for message in provider.requests[0]
    )
    assert "Add a greeting argument." in prompt
    assert "return 'hello'" in prompt
    assert "not-for-the-agent" not in prompt
    assert "failed validation" in provider.messages[-1]["content"]
    assert "src/app.py" in provider.messages[-1]["content"]
    assert "line 1" in provider.messages[-1]["content"]
    assert "character-for-character" in provider.messages[-1]["content"]
    assert len(provider.requests) == 2
    assert source_file.read_text(encoding="utf-8") == "def greet():\n    return 'hello'\n"


@pytest.mark.parametrize(
    ("file_name", "expected_code"),
    [
        ("../outside.py", "INVALID_FILE_PATH"),
        (".env", "FILE_NOT_ALLOWED"),
        ("secrets/settings.py", "FILE_NOT_ALLOWED"),
    ],
)
def test_coding_agent_rejects_paths_outside_safe_source_files(
    tmp_path,
    file_name,
    expected_code,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / ".env").write_text("SECRET=value", encoding="utf-8")
    secrets = workspace / "secrets"
    secrets.mkdir()
    (secrets / "settings.py").write_text("SECRET=value", encoding="utf-8")
    agent = CodingAgent(FakeProvider(), workspace)

    with pytest.raises(CodingAgentError) as error:
        agent.propose("Inspect this file.", [file_name])

    assert error.value.code == expected_code


def test_coding_agent_validates_file_list_and_model(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "main.py").write_text("pass\n", encoding="utf-8")
    agent = CodingAgent(FakeProvider(), workspace)

    with pytest.raises(CodingAgentError) as invalid_files:
        agent.propose("Inspect this file.", [{}])
    assert invalid_files.value.code == "INVALID_FILES"

    with pytest.raises(CodingAgentError) as invalid_model:
        agent.propose(
            "Inspect this file.",
            ["main.py"],
            model="not-installed",
        )
    assert invalid_model.value.code == "MODEL_NOT_FOUND"


def test_coding_agent_validates_new_file_proposals(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text("Project overview.\n", encoding="utf-8")
    provider = FakeProvider()
    provider.responses = [
        (
            "Summary\n```diff\n"
            "diff --git a/new.py b/new.py\n"
            "new file mode 100644\n"
            "--- /dev/null\n"
            "+++ b/new.py\n"
            "@@ -0,0 +1,2 @@\n"
            "+def answer():\n"
            "+    return 42\n"
            "```"
        )
    ]
    agent = CodingAgent(provider, workspace)

    result = agent.propose("Create a small answer helper.", ["README.md"])

    assert result["applied"] is False
    assert "b/new.py" in result["proposal"]
    assert not (workspace / "new.py").exists()
    agent.apply_proposal(result["proposal_id"])
    assert (workspace / "new.py").read_text(encoding="utf-8") == (
        "def answer():\n    return 42\n"
    )


def test_coding_agent_rejects_untrusted_paths_in_proposals(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source_file = workspace / "main.py"
    source_file.write_text("pass\n", encoding="utf-8")
    invalid_proposal = (
        "```diff\n"
        "--- a/../../outside.py\n"
        "+++ b/../../outside.py\n"
        "@@ -0,0 +1 @@\n"
        "+unsafe\n"
        "```"
    )
    provider = FakeProvider()
    provider.responses = [invalid_proposal, invalid_proposal]
    agent = CodingAgent(provider, workspace)

    with pytest.raises(CodingAgentError) as error:
        agent.propose("Add a file.", ["main.py"])

    assert error.value.code == "INVALID_PROPOSAL"
    assert source_file.read_text(encoding="utf-8") == "pass\n"


def test_coding_agent_creates_projects_and_saves_scoped_files(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    agent = CodingAgent(FakeProvider(), workspace)

    project = agent.create_project("New App")

    assert project == {"id": "New App", "name": "New App"}
    assert agent.list_projects()["projects"] == [
        {"id": ".", "name": "Workspace root"},
        {"id": "New App", "name": "New App"},
    ]
    assert agent.list_files("New App")["files"] == []

    created = agent.write_file(
        "New App/main.py",
        "print('hello')\n",
        create=True,
    )
    assert created["saved"] is True
    assert agent.read_file("New App/main.py")["content"] == "print('hello')\n"
    assert agent.list_files("New App")["files"] == ["New App/main.py"]

    agent.write_file(
        "New App/main.py",
        "print('updated')\n",
        expected_content="print('hello')\n",
    )
    assert (workspace / "New App" / "main.py").read_text(encoding="utf-8") == (
        "print('updated')\n"
    )


def test_coding_agent_rejects_unsafe_projects_and_stale_editor_saves(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "main.py").write_text("print('hello')\n", encoding="utf-8")
    agent = CodingAgent(FakeProvider(), workspace)

    for name in ("../outside", ".git", "bad/name", "trailing "):
        with pytest.raises(CodingAgentError):
            agent.create_project(name)

    with pytest.raises(CodingAgentError) as stale:
        agent.write_file(
            "main.py",
            "print('stale')\n",
            expected_content="older content\n",
        )
    assert stale.value.code == "FILE_CHANGED"
    assert (workspace / "main.py").read_text(encoding="utf-8") == "print('hello')\n"

    with pytest.raises(CodingAgentError) as outside:
        agent.write_file(
            "../outside.py",
            "pass\n",
            create=True,
        )
    assert outside.value.code == "INVALID_FILE_PATH"


def test_coding_agent_reports_unprefixed_hunk_lines(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    agent = CodingAgent(FakeProvider(), workspace)
    proposal = (
        "```diff\n"
        "--- a/main.py\n"
        "+++ b/main.py\n"
        "@@ -1 +1 @@\n"
        "pass\n"
        "```"
    )

    assert agent._validate_proposal(proposal, {"main.py": "pass\n"}) == (
        "A diff hunk contains an invalid line at diff line 4 "
        "(first character 'p')."
    )


def test_coding_agent_normalizes_blank_context_lines(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "main.py").write_text("first\n\nlast\n", encoding="utf-8")
    provider = FakeProvider()
    provider.responses = [
        (
            "Summary\n```diff\n"
            "--- a/main.py\n"
            "+++ b/main.py\n"
            "@@ -1,2 +1,2 @@\n"
            " first\n"
            "\n"
            "-last\n"
            "+LAST\n"
            "```"
        )
    ]
    agent = CodingAgent(provider, workspace)

    result = agent.propose("Uppercase the last line.", ["main.py"])

    assert "@@ -1,3 +1,3 @@" in result["proposal"]
    assert result["proposal"].count("\n \n") == 1
    assert result["applied"] is False


def test_coding_agent_applies_only_after_explicit_manual_approval(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source_file = workspace / "main.py"
    source_file.write_text("print('hello')\n", encoding="utf-8")
    provider = FakeProvider()
    provider.responses = [
        (
            "Summary\n```diff\n"
            "diff --git a/main.py b/main.py\n"
            "--- a/main.py\n"
            "+++ b/main.py\n"
            "@@ -1 +1 @@\n"
            "-print('hello')\n"
            "+print('Hello')\n"
            "```"
        )
    ]
    agent = CodingAgent(provider, workspace)

    proposal = agent.propose("Improve the greeting.", ["main.py"])

    assert proposal["permission_mode"] == "manual"
    assert proposal["status"] == "pending"
    assert source_file.read_text(encoding="utf-8") == "print('hello')\n"

    applied = agent.apply_proposal(proposal["proposal_id"])

    assert applied["applied"] is True
    assert applied["status"] == "applied"
    assert source_file.read_text(encoding="utf-8") == "print('Hello')\n"


def test_coding_agent_rejects_stale_proposals(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source_file = workspace / "main.py"
    source_file.write_text("print('hello')\n", encoding="utf-8")
    provider = FakeProvider()
    provider.responses = [
        (
            "Summary\n```diff\n"
            "--- a/main.py\n"
            "+++ b/main.py\n"
            "@@ -1 +1 @@\n"
            "-print('hello')\n"
            "+print('Hello')\n"
            "```"
        )
    ]
    agent = CodingAgent(provider, workspace)
    proposal = agent.propose("Improve the greeting.", ["main.py"])
    source_file.write_text("print('newer')\n", encoding="utf-8")

    with pytest.raises(CodingAgentError) as error:
        agent.apply_proposal(proposal["proposal_id"])

    assert error.value.code == "FILE_CHANGED"
    assert source_file.read_text(encoding="utf-8") == "print('newer')\n"


def test_coding_agent_preserves_crlf_when_applying_a_patch(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source_file = workspace / "main.py"
    source_file.write_bytes(b"print('hello')\r\n")
    provider = FakeProvider()
    provider.responses = [
        (
            "Summary\n```diff\n"
            "--- a/main.py\n"
            "+++ b/main.py\n"
            "@@ -1 +1 @@\n"
            "-print('hello')\n"
            "+print('Hello')\n"
            "```"
        )
    ]
    agent = CodingAgent(provider, workspace)
    proposal = agent.propose("Improve the greeting.", ["main.py"])

    agent.apply_proposal(proposal["proposal_id"])

    assert source_file.read_bytes() == b"print('Hello')\r\n"


def test_coding_agent_applies_a_validated_multi_file_patch(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    first_file = workspace / "first.py"
    second_file = workspace / "second.py"
    first_file.write_text("first = 1\n", encoding="utf-8")
    second_file.write_text("second = 2\n", encoding="utf-8")
    provider = FakeProvider()
    provider.responses = [
        (
            "Summary\n```diff\n"
            "diff --git a/first.py b/first.py\n"
            "--- a/first.py\n"
            "+++ b/first.py\n"
            "@@ -1 +1 @@\n"
            "-first = 1\n"
            "+first = 3\n"
            "diff --git a/second.py b/second.py\n"
            "--- a/second.py\n"
            "+++ b/second.py\n"
            "@@ -1 +1 @@\n"
            "-second = 2\n"
            "+second = 4\n"
            "```"
        )
    ]
    agent = CodingAgent(provider, workspace)
    proposal = agent.propose(
        "Update both values.",
        ["first.py", "second.py"],
    )

    agent.apply_proposal(proposal["proposal_id"])

    assert first_file.read_text(encoding="utf-8") == "first = 3\n"
    assert second_file.read_text(encoding="utf-8") == "second = 4\n"


def test_coding_agent_rejects_pending_proposal_without_writing(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source_file = workspace / "main.py"
    source_file.write_text("print('hello')\n", encoding="utf-8")
    provider = FakeProvider()
    provider.responses = [
        (
            "Summary\n```diff\n"
            "--- a/main.py\n"
            "+++ b/main.py\n"
            "@@ -1 +1 @@\n"
            "-print('hello')\n"
            "+print('Hello')\n"
            "```"
        )
    ]
    agent = CodingAgent(provider, workspace)
    proposal = agent.propose("Improve the greeting.", ["main.py"])

    result = agent.reject_proposal(proposal["proposal_id"])

    assert result["status"] == "rejected"
    assert source_file.read_text(encoding="utf-8") == "print('hello')\n"


def test_coding_agent_auto_mode_requires_explicit_confirmation(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source_file = workspace / "main.py"
    source_file.write_text("print('hello')\n", encoding="utf-8")
    provider = FakeProvider()
    provider.responses = [
        (
            "Summary\n```diff\n"
            "--- a/main.py\n"
            "+++ b/main.py\n"
            "@@ -1 +1 @@\n"
            "-print('hello')\n"
            "+print('Hello')\n"
            "```"
        )
    ]
    agent = CodingAgent(provider, workspace)

    with pytest.raises(CodingAgentError) as error:
        agent.set_permission_mode("auto")
    assert error.value.code == "AUTO_APPLY_CONFIRMATION_REQUIRED"

    permissions = agent.set_permission_mode(
        "auto",
        confirm_auto_apply=True,
    )
    proposal = agent.propose("Improve the greeting.", ["main.py"])

    assert permissions["mode"] == "auto"
    assert permissions["command_execution"] is False
    assert permissions["external_tool_execution"] is False
    assert proposal["applied"] is True
    assert proposal["status"] == "applied"
    assert source_file.read_text(encoding="utf-8") == "print('Hello')\n"


def test_persisted_coding_proposal_permission_and_audit_survive_restart(
    tmp_path,
):
    workspace = tmp_path / "workspace"
    (workspace / "src").mkdir(parents=True)
    source_file = workspace / "src" / "app.py"
    source_file.write_text(
        "def greet():\n    return 'hello'\n",
        encoding="utf-8",
    )
    database_path = tmp_path / "coding.sqlite3"
    owner_id = hashlib.sha256(b"coding:owner").hexdigest()
    actor_id = hashlib.sha256(b"coding:actor").hexdigest()
    first_store = ChatStore(database_path)
    first_agent = CodingAgent(
        FakeProvider(),
        workspace,
        persistence_store=first_store,
    )

    proposal = first_agent.propose(
        "Update the greeting.",
        ["src/app.py"],
        owner_id=owner_id,
        actor_id=actor_id,
        project_id=".",
    )
    first_agent.set_permission_mode(
        "auto",
        confirm_auto_apply=True,
        actor_id=actor_id,
    )
    first_store.close()

    second_store = ChatStore(database_path)
    third_store = ChatStore(database_path)
    try:
        second_agent = CodingAgent(
            FakeProvider(),
            workspace,
            persistence_store=second_store,
        )
        stale_agent = CodingAgent(
            FakeProvider(),
            workspace,
            persistence_store=third_store,
        )
        assert second_agent.permissions()["mode"] == "auto"
        assert second_agent.permissions()["reset_on_restart"] is False

        with pytest.raises(CodingAgentError) as error:
            second_agent.apply_proposal(
                proposal["proposal_id"],
                owner_id="other-owner",
                actor_id="other-actor",
            )
        assert error.value.code == "PROPOSAL_NOT_FOUND"

        applied = second_agent.apply_proposal(
            proposal["proposal_id"],
            owner_id=owner_id,
            actor_id=actor_id,
        )
        assert applied["status"] == "applied"
        assert source_file.read_text(encoding="utf-8") == (
            "def greet():\n    return 'Hello'\n"
        )
        with pytest.raises(CodingAgentError) as stale_error:
            stale_agent.apply_proposal(
                proposal["proposal_id"],
                owner_id=owner_id,
                actor_id=actor_id,
            )
        assert stale_error.value.code == "PROPOSAL_NOT_FOUND"
        audit = second_store.list_coding_audit()
        assert {item["action"] for item in audit} == {
            "proposal_created",
            "permission_mode_set",
            "proposal_apply_started",
            "proposal_applied",
        }
        assert all(item["actor_id"] == actor_id for item in audit)
        assert "coding:owner" not in repr(audit)
    finally:
        second_store.close()
        third_store.close()


def test_live_coding_agents_sync_permission_and_proposal_state(tmp_path):
    workspace = tmp_path / "workspace"
    (workspace / "src").mkdir(parents=True)
    source_file = workspace / "src" / "app.py"
    source_file.write_text(
        "def greet():\n    return 'hello'\n",
        encoding="utf-8",
    )
    database_path = tmp_path / "coding.sqlite3"
    owner_id = hashlib.sha256(b"coding:owner").hexdigest()
    actor_id = hashlib.sha256(b"coding:actor").hexdigest()
    first_store = ChatStore(database_path)
    second_store = ChatStore(database_path)
    try:
        provider = FakeProvider()
        provider.responses = [
            (
                "Summary\n```diff\n"
                "diff --git a/src/app.py b/src/app.py\n"
                "--- a/src/app.py\n"
                "+++ b/src/app.py\n"
                "@@ -1,2 +1,2 @@\n"
                " def greet():\n"
                "-    return 'hello'\n"
                "+    return 'Hello'\n"
                "```"
            )
        ]
        first_agent = CodingAgent(
            provider,
            workspace,
            persistence_store=first_store,
        )
        second_agent = CodingAgent(
            FakeProvider(),
            workspace,
            persistence_store=second_store,
        )

        proposal = first_agent.propose(
            "Update the greeting.",
            ["src/app.py"],
            owner_id=owner_id,
            actor_id=actor_id,
        )
        first_agent.set_permission_mode(
            "auto",
            confirm_auto_apply=True,
            actor_id=actor_id,
        )
        assert second_agent.permissions()["mode"] == "auto"
        assert [
            item["proposal_id"]
            for item in second_agent.list_proposals(owner_id)
        ] == [proposal["proposal_id"]]

        rejected = second_agent.reject_proposal(
            proposal["proposal_id"],
            owner_id=owner_id,
            actor_id=actor_id,
        )
        assert rejected["status"] == "rejected"
        assert first_agent.list_proposals(owner_id) == []
        with pytest.raises(CodingAgentError) as error:
            first_agent.reject_proposal(
                proposal["proposal_id"],
                owner_id=owner_id,
                actor_id=actor_id,
            )
        assert error.value.code == "PROPOSAL_NOT_FOUND"
    finally:
        first_store.close()
        second_store.close()


def test_restart_does_not_replay_a_proposal_mid_apply(tmp_path):
    workspace = tmp_path / "workspace"
    (workspace / "src").mkdir(parents=True)
    source_file = workspace / "src" / "app.py"
    source_file.write_text(
        "def greet():\n    return 'hello'\n",
        encoding="utf-8",
    )
    database_path = tmp_path / "coding.sqlite3"
    owner_id = hashlib.sha256(b"coding:owner").hexdigest()
    actor_id = hashlib.sha256(b"coding:actor").hexdigest()
    first_store = ChatStore(database_path)
    first_agent = CodingAgent(
        FakeProvider(),
        workspace,
        persistence_store=first_store,
    )
    proposal = first_agent.propose(
        "Update the greeting.",
        ["src/app.py"],
        owner_id=owner_id,
        actor_id=actor_id,
    )
    assert first_store.claim_coding_proposal(
        proposal["proposal_id"],
        owner_id,
        actor_id,
        {"files": ["src/app.py"]},
    )
    first_store.close()

    second_store = ChatStore(database_path)
    try:
        second_agent = CodingAgent(
            FakeProvider(),
            workspace,
            persistence_store=second_store,
        )
        with pytest.raises(CodingAgentError) as error:
            second_agent.apply_proposal(
                proposal["proposal_id"],
                owner_id=owner_id,
                actor_id=actor_id,
            )
        assert error.value.code == "PROPOSAL_NOT_FOUND"
        assert source_file.read_text(encoding="utf-8") == (
            "def greet():\n    return 'hello'\n"
        )
        assert second_store.list_coding_audit()[0]["action"] == (
            "proposal_apply_interrupted"
        )
    finally:
        second_store.close()
