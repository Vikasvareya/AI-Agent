import { FormEvent, useEffect, useMemo, useState } from "react";
import "./coding-dashboard.css";

type Role = "admin" | "user";
type ModelOption = {
  id: string;
  name: string;
  provider: string;
};
type Permissions = {
  mode: "manual" | "auto";
  workspace_write: boolean;
  write_requires_approval: boolean;
  auto_apply: boolean;
  command_execution: boolean;
  external_tool_execution: boolean;
  reset_on_restart: boolean;
};
type Integration = {
  supported: boolean;
  connected: string[];
  status: string;
};
type Integrations = {
  skills: Integration;
  plugins: Integration;
  mcp: Integration;
  model_training: Integration;
};
type Proposal = {
  proposal: string;
  proposal_id: string;
  files: string[];
  model: string;
  permission_mode: "manual" | "auto";
  applied: boolean;
  status: "pending" | "applied";
};
type Project = { id: string; name: string };
type SessionMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};
type CodingSessionSummary = {
  id: string;
  project_id: string;
  title: string;
  created_at: string;
  updated_at: string;
};
type CodingSession = CodingSessionSummary & {
  messages: SessionMessage[];
};
type WorkspaceScreen = "conversation" | "workspace" | "customizations" | "automations";
type SettingsSection =
  | "General"
  | "Application"
  | "Appearance"
  | "Shortcuts"
  | "Notifications"
  | "Models"
  | "Browser"
  | "Projects"
  | "Conversations"
  | "Integrations";
type AppMenu = "Workspace" | "View" | "Window";

class DashboardApiError extends Error {
  readonly status: number;

  constructor(
    message: string,
    status: number,
  ) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  token = "",
): Promise<T> {
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body) headers.set("Content-Type", "application/json");
  const response = await fetch(path, {
    ...options,
    headers,
    credentials: "same-origin",
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new DashboardApiError(
      data.message || `Request failed (${response.status}).`,
      response.status,
    );
  }

  return data as T;
}

export function SharedCodingSession({ token }: { token: string }) {
  const [session, setSession] = useState<CodingSession | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void request<CodingSession>(
      `/v1/coding/shared/${encodeURIComponent(token)}`,
    )
      .then(setSession)
      .catch(reason => setError(messageOf(reason)))
      .finally(() => setLoading(false));
  }, [token]);

  return (
    <main className="coding-shared-page">
      <header>
        <a href="/coding/">AI Agent · Coding workspace</a>
        <span>Read-only shared session</span>
      </header>
      {loading ? (
        <p>Loading shared session…</p>
      ) : error || !session ? (
        <section className="coding-shared-empty" role="alert">
          <h1>Session unavailable</h1>
          <p>{error || "This share link is invalid or expired."}</p>
        </section>
      ) : (
        <section className="coding-shared-content">
          <span className="coding-eyebrow">READ-ONLY SHARE · {session.project_id}</span>
          <h1>{session.title}</h1>
          <p>Prompts and proposals are visible. This link expires after 7 days.</p>
          <div className="coding-shared-messages">
            {session.messages.map(message => (
              <article
                key={message.id}
                className={`coding-shared-message ${message.role}`}
              >
                <strong>
                  {message.role === "user" ? "User" : "Agent proposal"}
                </strong>
                <pre>{message.content}</pre>
              </article>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}

function messageOf(reason: unknown): string {
  return reason instanceof Error ? reason.message : "Something went wrong.";
}

export default function CodingDashboard() {
  const [token, setToken] = useState("");
  const [tokenDraft, setTokenDraft] = useState("");
  const [role, setRole] = useState<Role | null>(null);
  const [available, setAvailable] = useState(false);
  const [files, setFiles] = useState<string[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState(".");
  const [projectName, setProjectName] = useState("");
  const [sessions, setSessions] = useState<CodingSessionSummary[]>([]);
  const [activeSession, setActiveSession] = useState<CodingSession | null>(null);
  const [sessionMessages, setSessionMessages] = useState<SessionMessage[]>([]);
  const [shareUrl, setShareUrl] = useState("");
  const [fileSearch, setFileSearch] = useState("");
  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);
  const [models, setModels] = useState<ModelOption[]>([]);
  const [defaultModel, setDefaultModel] = useState("");
  const [selectedModel, setSelectedModel] = useState("");
  const [permissions, setPermissions] = useState<Permissions | null>(null);
  const [integrations, setIntegrations] = useState<Integrations | null>(null);
  const [task, setTask] = useState("");
  const [taskKind, setTaskKind] = useState("Feature");
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [permissionBusy, setPermissionBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [editorPath, setEditorPath] = useState("");
  const [editorContent, setEditorContent] = useState("");
  const [editorOriginal, setEditorOriginal] = useState<string | null>(null);
  const [newFileName, setNewFileName] = useState("");
  const [editorPreview, setEditorPreview] = useState(false);
  const [editorBusy, setEditorBusy] = useState(false);
  const [activeScreen, setActiveScreen] = useState<WorkspaceScreen>("conversation");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsSection, setSettingsSection] = useState<SettingsSection>("General");
  const [filePickerOpen, setFilePickerOpen] = useState(false);
  const [permissionMenuOpen, setPermissionMenuOpen] = useState(false);
  const [openAppMenu, setOpenAppMenu] = useState<AppMenu | null>(null);
  const [projectCreateOpen, setProjectCreateOpen] = useState(false);
  const [customizationTab, setCustomizationTab] = useState<"marketplace" | "installed">("marketplace");

  useEffect(() => {
    const savedToken = sessionStorage.getItem("agent-token") || "";
    setToken(savedToken);
    void loadWorkspace(savedToken);
  }, []);

  const filteredFiles = useMemo(() => {
    const query = fileSearch.trim().toLowerCase();
    return query ? files.filter(file => file.toLowerCase().includes(query)) : files;
  }, [files, fileSearch]);

  async function loadFiles(projectId = selectedProject, authToken = token) {
    const result = await request<{ files: string[] }>(
      `/v1/coding/files?project=${encodeURIComponent(projectId)}`,
      {},
      authToken,
    );
    setFiles(result.files);
  }

  async function loadSessions(authToken = token, projectId = selectedProject) {
    const result = await request<{ sessions: CodingSessionSummary[] }>(
      `/v1/coding/sessions?project=${encodeURIComponent(projectId)}`,
      {},
      authToken,
    );
    setSessions(result.sessions);
    if (
      activeSession &&
      activeSession.project_id === projectId &&
      result.sessions.some(session => session.id === activeSession.id)
    ) {
      return;
    }
    setActiveSession(null);
    setSessionMessages([]);
    setShareUrl("");
  }

  async function openSession(sessionId: string) {
    setError("");
    try {
      const session = await request<CodingSession>(
        `/v1/coding/sessions/${encodeURIComponent(sessionId)}`,
        {},
        token,
      );
      setActiveSession(session);
      setSessionMessages(session.messages);
      setSelectedFiles([]);
      setTask("");
      setShareUrl("");
      setProposal(null);
    } catch (reason) {
      setError(messageOf(reason));
    }
  }

  async function createSession() {
    setError("");
    try {
      const session = await request<CodingSession>(
        "/v1/coding/sessions",
        {
          method: "POST",
          body: JSON.stringify({
            project_id: selectedProject,
            title: "New session",
          }),
        },
        token,
      );
      setSessions(current => [session, ...current]);
      setActiveSession(session);
      setSessionMessages([]);
      setSelectedFiles([]);
      setTask("");
      setShareUrl("");
      setProposal(null);
      setActiveScreen("conversation");
    } catch (reason) {
      setError(messageOf(reason));
    }
  }

  async function selectProject(projectId: string) {
    setSelectedProject(projectId);
    localStorage.setItem("coding-project", projectId);
    setSelectedFiles([]);
    setEditorPath("");
    setEditorContent("");
    setEditorOriginal(null);
    setProposal(null);
    setActiveSession(null);
    setSessionMessages([]);
    setShareUrl("");
    setError("");
    try {
      await Promise.all([
        loadFiles(projectId),
        loadSessions(token, projectId),
      ]);
    } catch (reason) {
      setError(messageOf(reason));
    }
  }

  async function createProject(event: FormEvent) {
    event.preventDefault();
    if (!projectName.trim()) return;
    setError("");
    try {
      const project = await request<Project>(
        "/v1/coding/projects",
        {
          method: "POST",
          body: JSON.stringify({ name: projectName.trim() }),
        },
        token,
      );
      setProjects(current =>
        [...current, project].sort((a, b) => a.name.localeCompare(b.name)),
      );
      setProjectName("");
      setProjectCreateOpen(false);
      await selectProject(project.id);
      setSuccess(`Project "${project.name}" created in the configured workspace.`);
    } catch (reason) {
      setError(messageOf(reason));
    }
  }

  async function shareSession() {
    if (
      !activeSession ||
      !window.confirm(
        "Anyone with this link can read this session's prompts and proposals for 7 days. Create a public read-only link?",
      )
    ) {
      return;
    }
    setError("");
    try {
      const result = await request<{ token: string; expires_at: string }>(
        `/v1/coding/sessions/${encodeURIComponent(activeSession.id)}/share`,
        { method: "POST", body: "{}" },
        token,
      );
      setShareUrl(`${window.location.origin}/coding/share/${result.token}`);
    } catch (reason) {
      setError(messageOf(reason));
    }
  }

  async function copyShareLink() {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setSuccess("Read-only share link copied.");
    } catch (reason) {
      setError(messageOf(reason));
    }
  }

  async function revokeSessionShares() {
    if (
      !activeSession ||
      !window.confirm("Revoke every share link for this session?")
    ) {
      return;
    }
    setError("");
    try {
      await request(
        `/v1/coding/sessions/${encodeURIComponent(activeSession.id)}/shares`,
        { method: "DELETE" },
        token,
      );
      setShareUrl("");
      setSuccess("All share links for this session were revoked.");
    } catch (reason) {
      setError(messageOf(reason));
    }
  }

  async function loadWorkspace(authToken = token) {
    setLoading(true);
    setError("");
    try {
      const account = await request<{ role: Role }>("/v1/session", {}, authToken);
      setRole(account.role);
      if (account.role !== "admin") {
        throw new DashboardApiError("Administrator access is required.", 403);
      }
      const [status, projectCatalog, modelCatalog, permissionState, integrationState] =
        await Promise.all([
          request<{ available: boolean; reason?: string }>("/v1/coding/status", {}, authToken),
          request<{ projects: Project[] }>("/v1/coding/projects", {}, authToken),
          request<{ default_model: string; models: ModelOption[] }>("/v1/coding/models", {}, authToken),
          request<Permissions>("/v1/coding/permissions", {}, authToken),
          request<Integrations>("/v1/coding/integrations", {}, authToken),
        ]);
      setAvailable(status.available);
      if (!status.available) {
        throw new DashboardApiError(
          status.reason || "Configure a coding workspace to continue.",
          503,
        );
      }

      setProjects(projectCatalog.projects);
      const savedProject = localStorage.getItem("coding-project") || selectedProject;
      const projectId = projectCatalog.projects.some(project => project.id === savedProject)
        ? savedProject
        : ".";
      setSelectedProject(projectId);
      localStorage.setItem("coding-project", projectId);
      setModels(modelCatalog.models);
      setDefaultModel(modelCatalog.default_model);
      setSelectedModel(current =>
        modelCatalog.models.some(model => model.id === current)
          ? current
          : modelCatalog.default_model,
      );
      setPermissions(permissionState);
      setIntegrations(integrationState);
      await Promise.all([
        loadFiles(projectId, authToken),
        loadSessions(authToken, projectId),
      ]);
    } catch (reason) {
      setError(messageOf(reason));
      if (reason instanceof DashboardApiError && reason.status === 401) {
        setRole(null);
      }

    } finally {
      setLoading(false);
    }
  }

  async function signIn(event: FormEvent) {
    event.preventDefault();
    const candidate = tokenDraft.trim();
    if (!candidate) return;
    setToken(candidate);
    sessionStorage.setItem("agent-token", candidate);
    setTokenDraft("");
    await loadWorkspace(candidate);
  }

  async function updatePermissionMode(mode: "manual" | "auto") {
    if (
      mode === "auto" &&
      !window.confirm(
        "Auto mode applies validated patches directly to this configured workspace. It does not run shell commands or invoke external tools. Continue?",
      )
    ) {
      return;
    }
    setPermissionBusy(true);
    setError("");
    setSuccess("");
    try {
      const result = await request<Permissions>(
        "/v1/coding/permissions",
        {
          method: "POST",
          body: JSON.stringify({
            mode,
            confirm_auto_apply: mode === "auto",
          }),
        },
        token,
      );
      setPermissions(result);
      setSuccess(
        mode === "auto"
          ? "Auto mode enabled for validated workspace patches."
          : "Manual review is enabled. Every patch requires your approval.",
      );
    } catch (reason) {
      setError(messageOf(reason));
    } finally {
      setPermissionBusy(false);
    }
  }

  async function generateProposal(event: FormEvent) {
    event.preventDefault();
    if (!task.trim() || selectedFiles.length === 0 || !activeSession || busy) return;
    setBusy(true);
    setError("");
    setSuccess("");
    setProposal(null);
    try {
      const result = await request<Proposal>(
        "/v1/coding/proposals",
        {
          method: "POST",
          body: JSON.stringify({
            task: `Task type: ${taskKind}\n\n${task.trim()}`,
            files: selectedFiles,
            model: selectedModel || undefined,
            project_id: selectedProject,
            session_id: activeSession.id,
          }),
        },
        token,
      );
      setProposal(result);
      setActiveScreen("conversation");
      const updatedSession = await request<CodingSession>(
        `/v1/coding/sessions/${encodeURIComponent(activeSession.id)}`,
        {},
        token,
      );
      setActiveSession(updatedSession);
      setSessionMessages(updatedSession.messages);
      setSessions(current =>
        current.map(session =>
          session.id === updatedSession.id ? updatedSession : session,
        ),
      );
      if (result.applied) {
        setSuccess("The validated patch was applied to the configured workspace.");
        await reloadFiles();
      }
    } catch (reason) {
      setError(messageOf(reason));
    } finally {
      setBusy(false);
    }
  }

  async function reloadFiles() {
    const result = await request<{ files: string[] }>(
      `/v1/coding/files?project=${encodeURIComponent(selectedProject)}`,
      {},
      token,
    );
    setFiles(result.files);
  }

  async function openFile(file: string) {
    setError("");
    setEditorPreview(false);
    try {
      const result = await request<{ path: string; content: string }>(
        `/v1/coding/file?path=${encodeURIComponent(file)}`,
        {},
        token,
      );
      setEditorPath(result.path);
      setEditorContent(result.content);
      setEditorOriginal(result.content);
    } catch (reason) {
      setError(messageOf(reason));
    }
  }

  function startNewFile(event: FormEvent) {
    event.preventDefault();
    const name = newFileName.trim().replace(/\\/g, "/");
    if (!name) return;
    const path = selectedProject === "." ? name : `${selectedProject}/${name}`;
    setEditorPath(path);
    setEditorContent("");
    setEditorOriginal(null);
    setEditorPreview(false);
    setNewFileName("");
  }

  async function saveFile() {
    if (!editorPath || editorBusy) return;
    setEditorBusy(true);
    setError("");
    setSuccess("");
    try {
      await request(
        "/v1/coding/file",
        {
          method: "POST",
          body: JSON.stringify({
            path: editorPath,
            content: editorContent,
            expected_content: editorOriginal,
            create: editorOriginal === null,
          }),
        },
        token,
      );
      setEditorOriginal(editorContent);
      setSuccess(`Saved ${editorPath}.`);
      await reloadFiles();
    } catch (reason) {
      setError(messageOf(reason));
    } finally {
      setEditorBusy(false);
    }
  }

  async function decideProposal(decision: "apply" | "reject") {
    if (!proposal || busy) return;
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      const result = await request<{ applied?: boolean; status: string }>(
        `/v1/coding/proposals/${proposal.proposal_id}/${decision}`,
        { method: "POST", body: "{}" },
        token,
      );
      setProposal(current =>
        current ? { ...current, applied: result.applied === true, status: result.status as Proposal["status"] } : current,
      );
      setSuccess(
        decision === "apply"
          ? "Patch applied. Changed files were rechecked before writing."
          : "Proposal rejected; workspace files were not changed.",
      );
      if (decision === "apply") await reloadFiles();
    } catch (reason) {
      setError(messageOf(reason));
    } finally {
      setBusy(false);
    }
  }

  function toggleFile(file: string, checked: boolean) {
    setSelectedFiles(current => {
      if (checked && current.length < 8) return [...current, file];
      return current.filter(selected => selected !== file);
    });
    setProposal(null);
  }

  return (
    <div className="coding-dashboard coding-app">
      <header className="coding-appbar">
        <a className="coding-window-brand" href="/chat/" aria-label="AI Agent home">
          <span className="coding-brand-mark">✦</span>
          <strong>AI Agent</strong>
        </a>
        {(["Workspace", "View", "Window"] as const).map(menu => (
          <div className="coding-app-menu" key={menu}>
            <button
              type="button"
              className={openAppMenu === menu ? "selected" : ""}
              onClick={() => setOpenAppMenu(current => current === menu ? null : menu)}
              aria-expanded={openAppMenu === menu}
            >
              {menu}
            </button>
            {openAppMenu === menu && (
              <div className="coding-app-menu-popover">
                {menu === "Workspace" && (
                  <>
                    <button type="button" onClick={() => { setOpenAppMenu(null); void createSession(); }}>New conversation</button>
                    <button type="button" onClick={() => { setOpenAppMenu(null); setActiveScreen("workspace"); }}>Open workbench</button>
                    <button type="button" onClick={() => { setOpenAppMenu(null); setProjectCreateOpen(true); }}>Create project</button>
                  </>
                )}
                {menu === "View" && (
                  <>
                    <button type="button" onClick={() => { setOpenAppMenu(null); setActiveScreen("conversation"); }}>Conversation</button>
                    <button type="button" onClick={() => { setOpenAppMenu(null); setActiveScreen("workspace"); }}>Workbench</button>
                    <button type="button" onClick={() => { setOpenAppMenu(null); setActiveScreen("customizations"); }}>Customizations</button>
                  </>
                )}
                {menu === "Window" && (
                  <>
                    <button type="button" onClick={() => { setOpenAppMenu(null); setSettingsOpen(true); }}>Settings</button>
                    <button type="button" onClick={() => { setOpenAppMenu(null); void loadWorkspace(); }}>Refresh workspace</button>
                  </>
                )}
              </div>
            )}
          </div>
        ))}
        <div className="coding-appbar-spacer" />
        <span className={`coding-state ${available ? "connected" : ""}`}>
          <i /> {available ? "Workspace connected" : "Workspace unavailable"}
        </span>
      </header>

      <div className="coding-shell">
        <aside className="coding-sidebar">
          <button
            type="button"
            className="coding-new-conversation"
            onClick={() => void createSession()}
            disabled={role !== "admin" || loading}
          >
            <span>＋</span> New Conversation
          </button>
          <nav className="coding-primary-nav" aria-label="Workspace navigation">
            <button type="button" onClick={() => setActiveScreen("automations")} className={activeScreen === "automations" ? "selected" : ""}>
              <span>◷</span> Automations <small>Planned</small>
            </button>
            <button type="button" onClick={() => setActiveScreen("customizations")} className={activeScreen === "customizations" ? "selected" : ""}>
              <span>▣</span> Customizations
            </button>
          </nav>

          {role === "admin" && (
            <>
              <section className="coding-tree-section">
                <div className="coding-tree-heading">
                  <span>Projects</span>
                  <button
                    type="button"
                    title="Create project"
                    aria-label="Create project"
                    onClick={() => setProjectCreateOpen(value => !value)}
                  >
                    ＋
                  </button>
                </div>
                {projectCreateOpen && (
                  <form className="coding-project-create" onSubmit={event => void createProject(event)}>
                    <input
                      aria-label="New project name"
                      value={projectName}
                      maxLength={64}
                      onChange={event => setProjectName(event.target.value)}
                      placeholder="Project name"
                      autoFocus
                    />
                    <button type="submit" disabled={!projectName.trim()}>Add</button>
                  </form>
                )}
                <div className="coding-project-tree">
                  {projects.map(project => (
                    <button
                      type="button"
                      className={`coding-project-tree-item ${selectedProject === project.id ? "selected" : ""}`}
                      key={project.id}
                      onClick={() => void selectProject(project.id)}
                      title={project.name}
                    >
                      <span>{selectedProject === project.id ? "▾" : "▸"}</span>
                      <span className="coding-tree-folder">▱</span>
                      <span className="coding-tree-name">{project.name}</span>
                    </button>
                  ))}
                </div>
              </section>
              <section className="coding-tree-section coding-conversation-tree">
                <div className="coding-tree-heading">
                  <span>Conversations</span>
                  <button type="button" title="New conversation" aria-label="New conversation" onClick={() => void createSession()}>＋</button>
                </div>
                <div className="coding-session-list">
                  {sessions.map(session => (
                    <button
                      type="button"
                      className={`coding-session-item ${activeSession?.id === session.id ? "selected" : ""}`}
                      key={session.id}
                      onClick={() => { setActiveScreen("conversation"); void openSession(session.id); }}
                      title={session.title}
                    >
                      <span>{session.title}</span>
                      {activeSession?.id === session.id && <small>Now</small>}
                    </button>
                  ))}
                  {!sessions.length && <small className="coding-sidebar-empty">No conversations yet</small>}
                </div>
              </section>
            </>
          )}
          <div className="coding-sidebar-bottom">
            <button type="button" className="coding-settings-trigger" onClick={() => { setSettingsSection("General"); setSettingsOpen(true); }}>
              <span>⚙</span> Settings
            </button>
            <div className="coding-admin-badge"><span /> {role === "admin" ? "Administrator" : "Workspace sign in required"}</div>
          </div>
        </aside>

      <main className="coding-main" id="overview">
        <header className="coding-topbar">
          <div className="coding-top-actions">
            <span className="coding-location">{projects.find(project => project.id === selectedProject)?.name || "Project workspace"}{activeSession ? ` / ${activeSession.title}` : ""}</span>
            <button type="button" className="coding-secondary" onClick={() => setActiveScreen("workspace")}>Workspace</button>
            {activeSession && (
              <>
                <button type="button" className="coding-secondary" onClick={() => void shareSession()} disabled={!sessionMessages.length}>Share</button>
                <button type="button" className="coding-secondary" onClick={() => void revokeSessionShares()} disabled={!activeSession}>Revoke</button>
              </>
            )}
            <button type="button" className="coding-refresh" onClick={() => void loadWorkspace()} disabled={loading}>
              {loading ? "Refreshing…" : "↻"}
            </button>
          </div>
        </header>

        {error && <div className="coding-banner error" role="alert">{error}</div>}
        {success && <div className="coding-banner success" role="status">{success}</div>}

        {loading ? (
          <section className="coding-loading"><span className="coding-spinner" /> Loading workspace…</section>
        ) : role !== "admin" ? (
          <section className="coding-auth-card">
            <div className="coding-auth-icon">⌑</div>
            <h2>Administrator access</h2>
            <p>Sign in with an administrator token to browse files and manage coding permissions.</p>
            <form onSubmit={event => void signIn(event)}>
              <label htmlFor="coding-admin-token">Admin token</label>
              <input
                id="coding-admin-token"
                type="password"
                autoComplete="current-password"
                value={tokenDraft}
                onChange={event => setTokenDraft(event.target.value)}
                placeholder="Paste your administrator token"
                required
              />
              <button type="submit" className="coding-primary">Connect workspace</button>
            </form>
          </section>
        ) : activeScreen === "conversation" ? (
          <section className="coding-conversation-screen" id="conversation">
            <div className="coding-conversation-scroll">
              {sessionMessages.length ? (
                <div className="coding-message-list">
                  {sessionMessages.map(message => (
                    <article className={`coding-message ${message.role}`} key={message.id}>
                      <span className="coding-message-avatar">{message.role === "user" ? "You" : "✦"}</span>
                      <div className="coding-message-body">
                        <strong>{message.role === "user" ? "You" : "AI Agent"}</strong>
                        <pre>{message.content}</pre>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="coding-conversation-welcome">
                  <div className="coding-welcome-symbol">✦</div>
                  <h1>What should we build today?</h1>
                  <p>
                    {activeSession
                      ? `Working in ${projects.find(project => project.id === selectedProject)?.name || "your project"}. Select files, describe a task, and review the proposed patch.`
                      : "Start a conversation to plan a task, inspect files, and review a workspace-scoped patch."}
                  </p>
                  {!activeSession && (
                    <button type="button" className="coding-primary" onClick={() => void createSession()}>
                      New conversation <span>→</span>
                    </button>
                  )}
                  {activeSession && (
                    <div className="coding-welcome-hints">
                      <span>⌘ Select files for context</span>
                      <span>◈ Manual review is the default</span>
                    </div>
                  )}
                </div>
              )}
              {proposal && (
                <section className="coding-panel coding-proposal-panel coding-live-proposal" aria-live="polite">
                  <div className="coding-panel-heading">
                    <div><span className="coding-panel-icon">⌘</span><div><h2>Review proposal</h2><p>{proposal.files.join(", ")} · {proposal.model}</p></div></div>
                    <span className={`coding-proposal-status ${proposal.applied ? "applied" : ""}`}>{proposal.status}</span>
                  </div>
                  <pre>{proposal.proposal}</pre>
                  {!proposal.applied && proposal.status === "pending" && (
                    <div className="coding-proposal-actions">
                      <span>Review the patch before applying it to the workspace.</span>
                      <div>
                        <button type="button" className="coding-secondary" onClick={() => void decideProposal("reject")} disabled={busy}>Reject</button>
                        <button type="button" className="coding-primary" onClick={() => void decideProposal("apply")} disabled={busy}>Apply patch</button>
                      </div>
                    </div>
                  )}
                </section>
              )}
            </div>

            <div className="coding-composer-dock">
              {shareUrl && (
                <div className="coding-share-link coding-share-link-inline">
                  <label htmlFor="coding-share-url">Read-only link (expires in 7 days)</label>
                  <input id="coding-share-url" value={shareUrl} readOnly onFocus={event => event.currentTarget.select()} />
                  <button type="button" className="coding-secondary" onClick={() => void copyShareLink()}>Copy</button>
                </div>
              )}
              {filePickerOpen && (
                <section className="coding-file-picker" aria-label="Select workspace files">
                  <header>
                    <div><strong>Add files to context</strong><small>{selectedFiles.length} of 8 selected</small></div>
                    <button type="button" onClick={() => setFilePickerOpen(false)} aria-label="Close file picker">×</button>
                  </header>
                  <input
                    type="search"
                    className="coding-search"
                    value={fileSearch}
                    onChange={event => setFileSearch(event.target.value)}
                    placeholder="Search project files"
                    aria-label="Search project files"
                  />
                  <div className="coding-file-list">
                    {filteredFiles.map(file => (
                      <label className="coding-file-option" key={file}>
                        <input
                          type="checkbox"
                          checked={selectedFiles.includes(file)}
                          disabled={!selectedFiles.includes(file) && selectedFiles.length >= 8}
                          onChange={event => toggleFile(file, event.target.checked)}
                        />
                        <span className="coding-file-glyph">▱</span>
                        <span>{file}</span>
                      </label>
                    ))}
                    {!filteredFiles.length && <div className="coding-empty">No eligible files match this search.</div>}
                  </div>
                </section>
              )}
              <div className="coding-composer-context">
                <label>
                  <span>▱</span>
                  <select
                    id="coding-main-project"
                    value={selectedProject}
                    onChange={event => void selectProject(event.target.value)}
                    aria-label="Current project"
                  >
                    {projects.map(project => <option value={project.id} key={project.id}>{project.name}</option>)}
                  </select>
                </label>
                <span className="coding-context-divider">/</span>
                <label>
                  <span>◷</span>
                  <select
                    className="coding-active-session-select"
                    aria-label="Choose coding session"
                    value={activeSession?.id || ""}
                    onChange={event => {
                      if (event.target.value) void openSession(event.target.value);
                    }}
                  >
                    <option value="">Choose conversation</option>
                    {sessions.map(session => <option value={session.id} key={session.id}>{session.title}</option>)}
                  </select>
                </label>
                {activeSession && <small>{sessionMessages.length} saved context messages</small>}
              </div>
              <form className="coding-chat-composer" onSubmit={event => void generateProposal(event)}>
                <textarea
                  id="coding-task"
                  rows={2}
                  maxLength={4000}
                  value={task}
                  onChange={event => setTask(event.target.value)}
                  placeholder={activeSession ? "Ask anything about this project or describe a change…" : "Create a conversation to start a coding task…"}
                  aria-label="Describe a coding task"
                  disabled={!activeSession}
                />
                <div className="coding-chat-composer-tools">
                  <div className="coding-composer-left-tools">
                    <button
                      type="button"
                      className={`coding-composer-tool ${filePickerOpen ? "selected" : ""}`}
                      onClick={() => setFilePickerOpen(value => !value)}
                      title="Select up to 8 eligible project files"
                    >
                      ＋ <span>{selectedFiles.length ? `${selectedFiles.length} files` : "Add files"}</span>
                    </button>
                    <label className="coding-composer-select" aria-label="Task type">
                      <select value={taskKind} onChange={event => setTaskKind(event.target.value)}>
                        <option>Feature</option><option>Bug fix</option><option>Refactor</option><option>Tests</option><option>DSA problem</option>
                      </select>
                    </label>
                    <label className="coding-composer-select model" aria-label="Model">
                      <span>◉</span>
                      <select value={selectedModel} onChange={event => setSelectedModel(event.target.value)} disabled={!models.length}>
                        {models.map(model => <option value={model.id} key={model.id}>{model.name}</option>)}
                        {!models.length && <option value="">No models available</option>}
                      </select>
                    </label>
                  </div>
                  <div className="coding-composer-right-tools">
                    <div className="coding-permission-control">
                      <button
                        type="button"
                        className="coding-permission-trigger"
                        aria-expanded={permissionMenuOpen}
                        onClick={() => setPermissionMenuOpen(value => !value)}
                      >
                        ◈ {permissions?.mode === "auto" ? "Auto" : "Manual"} <span>⌄</span>
                      </button>
                      {permissionMenuOpen && (
                        <div className="coding-permission-menu">
                          <strong>Local permissions</strong>
                          <button type="button" onClick={() => { setPermissionMenuOpen(false); void updatePermissionMode("manual"); }}>
                            <span>◉</span><span><b>Manual review</b><small>Every patch needs your approval.</small></span>
                            {permissions?.mode === "manual" && <i>✓</i>}
                          </button>
                          <button type="button" onClick={() => { setPermissionMenuOpen(false); void updatePermissionMode("auto"); }}>
                            <span>◈</span><span><b>Auto-apply</b><small>Apply validated patches in this workspace.</small></span>
                            {permissions?.mode === "auto" && <i>✓</i>}
                          </button>
                          <p>Commands, plugins, and MCP tools remain disabled.</p>
                        </div>
                      )}
                    </div>
                    <button
                      className="coding-send-button"
                      type="submit"
                      aria-label="Generate coding proposal"
                      disabled={!task.trim() || selectedFiles.length === 0 || !activeSession || busy}
                      title={!selectedFiles.length ? "Select files before generating a proposal" : "Generate proposal"}
                    >
                      {busy ? "…" : "↑"}
                    </button>
                  </div>
                </div>
                <div className="coding-composer-footer">
                  <span>{selectedFiles.length ? `${selectedFiles.length} selected · only selected files are sent to the model` : "Select eligible files to give the agent scoped context"}</span>
                  <span>{task.length}/4000</span>
                </div>
              </form>
            </div>
          </section>
        ) : activeScreen === "customizations" ? (
          <section className="coding-settings-page">
            <header className="coding-page-heading">
              <div><span className="coding-eyebrow">WORKSPACE</span><h1>Customizations</h1><p>Review the integrations this deployment can use.</p></div>
              <div className="coding-segmented-control" role="tablist" aria-label="Customization view">
                <button type="button" role="tab" aria-selected={customizationTab === "marketplace"} className={customizationTab === "marketplace" ? "selected" : ""} onClick={() => setCustomizationTab("marketplace")}>Marketplace</button>
                <button type="button" role="tab" aria-selected={customizationTab === "installed"} className={customizationTab === "installed" ? "selected" : ""} onClick={() => setCustomizationTab("installed")}>Installed</button>
              </div>
            </header>
            {customizationTab === "marketplace" && (
              <article className="coding-custom-feature">
                <div className="coding-custom-art">✦</div>
                <div><span>INTEGRATION REGISTRY</span><h2>Connect tools with explicit permissions</h2><p>This deployment does not have a customization marketplace configured. No integrations can be installed from this screen.</p></div>
              </article>
            )}
            <h2 className="coding-section-title">{customizationTab === "installed" ? "Installed integrations" : "Available integration points"}</h2>
            <div className="coding-custom-grid">
              {integrations ? ([
                ["Skills", integrations.skills],
                ["Plugins", integrations.plugins],
                ["MCP servers", integrations.mcp],
              ] as const).map(([name, integration]) => (
                <article className="coding-custom-card" key={name}>
                  <div className="coding-custom-icon">{name === "Skills" ? "✧" : name === "Plugins" ? "◈" : "⌘"}</div>
                  <div className="coding-custom-card-title"><h3>{name}</h3><span>{integration.connected.length ? `${integration.connected.length} connected` : "Not connected"}</span></div>
                  <p>{integration.status}</p>
                  <small>{integration.supported ? "Supported integration point" : "Execution is not supported in this workspace"}</small>
                </article>
              )) : <p className="coding-empty">Integration status is loading.</p>}
            </div>
            <p className="coding-page-note">Tools are not invoked by the coding agent. Registry, review, and per-tool permission controls are planned.</p>
          </section>
        ) : activeScreen === "automations" ? (
          <section className="coding-settings-page coding-unavailable-page">
            <div className="coding-empty-icon">◷</div>
            <span className="coding-eyebrow">NOT CONFIGURED</span>
            <h1>Automations</h1>
            <p>Scheduled and background agent runs are not available in this deployment yet. Current coding tasks run only when you start them.</p>
            <button type="button" className="coding-secondary" onClick={() => setActiveScreen("conversation")}>Back to conversation</button>
          </section>
        ) : available && permissions ? (
          <div className="coding-workspace-scroll">
            <section className="coding-welcome">
              <div>
                <span className="coding-eyebrow">BUILD WITH CONTROL</span>
                <h2>Plan, review, and ship changes.</h2>
                <p>Keep work scoped to selected files, choose your model, then inspect every generated patch.</p>
              </div>
              <div className="coding-welcome-symbol">&lt;/&gt;</div>
            </section>

            <section className="coding-stats" aria-label="Workspace summary">
              <article><span>Eligible files</span><strong>{files.length}</strong><small>Secret and generated paths excluded</small></article>
              <article><span>Selected context</span><strong>{selectedFiles.length}<small> / 8</small></strong><small>Only selected files reach the model</small></article>
              <article><span>Permission mode</span><strong className={permissions.mode === "auto" ? "mode-auto" : ""}>{permissions.mode === "manual" ? "Manual" : "Auto"}</strong><small>{permissions.mode === "manual" ? "Review before writing" : "Validated patches apply automatically"}</small></article>
            </section>

            <section className="coding-session-toolbar">
              <div className="coding-project-main-control">
                <label htmlFor="coding-main-project">PROJECT</label>
                <select
                  id="coding-main-project"
                  value={selectedProject}
                  onChange={event => void selectProject(event.target.value)}
                >
                  {projects.map(project => (
                    <option value={project.id} key={project.id}>{project.name}</option>
                  ))}
                </select>
                <form onSubmit={event => void createProject(event)}>
                  <input
                    aria-label="Add project folder"
                    value={projectName}
                    maxLength={64}
                    onChange={event => setProjectName(event.target.value)}
                    placeholder="Add project"
                  />
                  <button type="submit" disabled={!projectName.trim()}>Create</button>
                </form>
              </div>
              <div>
                <span>ACTIVE SESSION</span>
                <select
                  className="coding-active-session-select"
                  aria-label="Choose coding session"
                  value={activeSession?.id || ""}
                  onChange={event => {
                    if (event.target.value) void openSession(event.target.value);
                  }}
                >
                  <option value="">Choose or create a session</option>
                  {sessions.map(session => (
                    <option value={session.id} key={session.id}>{session.title}</option>
                  ))}
                </select>
                <small>
                  {activeSession
                    ? `${sessionMessages.length} saved context messages`
                    : "Each session keeps its own prompts and proposals"}
                </small>
              </div>
              <div className="coding-session-actions">
                <button type="button" className="coding-secondary" onClick={() => void createSession()}>
                  New session
                </button>
                <button
                  type="button"
                  className="coding-secondary"
                  disabled={!activeSession || !sessionMessages.length}
                  onClick={() => void shareSession()}
                >
                  Share session
                </button>
                <button
                  type="button"
                  className="coding-secondary"
                  disabled={!activeSession}
                  onClick={() => void revokeSessionShares()}
                >
                  Revoke shares
                </button>
              </div>
              {shareUrl && (
                <div className="coding-share-link">
                  <label htmlFor="coding-share-url">Read-only link (expires in 7 days)</label>
                  <input id="coding-share-url" value={shareUrl} readOnly onFocus={event => event.currentTarget.select()} />
                  <button type="button" className="coding-secondary" onClick={() => void copyShareLink()}>Copy link</button>
                </div>
              )}
            </section>

            <div className="coding-content-grid" id="workbench">
              <section className="coding-panel coding-task-panel">
                <div className="coding-panel-heading">
                  <div><span className="coding-panel-icon">✦</span><div><h2>Start a task</h2><p>Describe the outcome; the agent proposes a scoped patch.</p></div></div>
                </div>
                <form onSubmit={event => void generateProposal(event)}>
                  <div className="coding-form-row">
                    <label>
                      Task type
                      <select value={taskKind} onChange={event => setTaskKind(event.target.value)}>
                        <option>Feature</option><option>Bug fix</option><option>Refactor</option><option>Tests</option><option>DSA problem</option>
                      </select>
                    </label>
                    <label>
                      Model
                      <select value={selectedModel} onChange={event => setSelectedModel(event.target.value)} disabled={!models.length}>
                        {models.map(model => <option value={model.id} key={model.id}>{model.name}</option>)}
                        {!models.length && <option value="">No models available</option>}
                      </select>
                    </label>
                  </div>
                  <label htmlFor="coding-task">What should the agent build?</label>
                  <textarea
                    id="coding-task"
                    rows={5}
                    maxLength={4000}
                    value={task}
                    onChange={event => setTask(event.target.value)}
                    placeholder="Describe the goal, constraints, and expected behavior…"
                  />
                  <div className="coding-task-meta"><span>{task.length}/4000 characters</span><span>Uses {defaultModel || "the configured model"} by default</span></div>
                  <div className="coding-selected-summary">
                    <span>Files in context</span>
                    <strong>{selectedFiles.length ? selectedFiles.join(", ") : "Select up to 8 files from the workspace"}</strong>
                  </div>
                  <button className="coding-primary" type="submit" disabled={!task.trim() || selectedFiles.length === 0 || !activeSession || busy}>
                    {busy ? "Working…" : "Generate proposal"} <span>→</span>
                  </button>
                  {!activeSession && <p className="coding-footnote">Create or choose a session before starting a task.</p>}
                </form>
              </section>

              <section className="coding-panel coding-files-panel">
                <div className="coding-panel-heading">
                  <div><span className="coding-panel-icon">▤</span><div><h2>Workspace files</h2><p>Choose the files the model can read and propose edits for.</p></div></div>
                  <span className="coding-count">{selectedFiles.length}/8</span>
                </div>
                <input
                  type="search"
                  className="coding-search"
                  value={fileSearch}
                  onChange={event => setFileSearch(event.target.value)}
                  placeholder="Filter by filename or folder…"
                  aria-label="Filter workspace files"
                />
                <form className="coding-new-file" onSubmit={event => startNewFile(event)}>
                  <input
                    aria-label="New file path"
                    value={newFileName}
                    maxLength={240}
                    onChange={event => setNewFileName(event.target.value)}
                    placeholder={selectedProject === "." ? "New file (e.g. src/app.py)" : "New file (e.g. src/app.py)"}
                  />
                  <button type="submit" disabled={!newFileName.trim()}>Create</button>
                </form>
                <div className="coding-file-list">
                  {filteredFiles.map(file => (
                    <div className="coding-file-row" key={file}>
                      <input
                        type="checkbox"
                        aria-label={`Add ${file} to coding context`}
                        checked={selectedFiles.includes(file)}
                        disabled={!selectedFiles.includes(file) && selectedFiles.length >= 8}
                        onChange={event => toggleFile(file, event.target.checked)}
                      />
                      <span className="coding-file-glyph">{file.split("/").length > 1 ? "▱" : "◧"}</span>
                      <span className="coding-file-name">{file}</span>
                      <button type="button" onClick={() => void openFile(file)}>Edit</button>
                    </div>
                  ))}
                  {!filteredFiles.length && <div className="coding-empty">No eligible files match this search.</div>}
                </div>
                <p className="coding-footnote">Credentials, dependency folders, and generated files are excluded.</p>
              </section>
            </div>

            <section className="coding-panel coding-editor-panel">
              <div className="coding-panel-heading">
                <div><span className="coding-panel-icon">⌨</span><div><h2>Workspace editor</h2><p>Edit and save an explicit file; HTML preview blocks scripts.</p></div></div>
                {editorPath && <span className="coding-count">{editorPath}</span>}
              </div>
              {editorPath ? (
                <>
                  <div className="coding-editor-toolbar">
                    <div>
                      <button type="button" className={!editorPreview ? "selected" : ""} onClick={() => setEditorPreview(false)}>Editor</button>
                      <button type="button" className={editorPreview ? "selected" : ""} onClick={() => setEditorPreview(true)}>Preview</button>
                    </div>
                    <button
                      type="button"
                      className="coding-primary"
                      onClick={() => void saveFile()}
                      disabled={editorBusy || editorContent === editorOriginal}
                    >
                      {editorBusy ? "Saving…" : editorOriginal === null ? "Create file" : "Save file"}
                    </button>
                  </div>
                  {editorPreview ? (
                    editorPath.toLowerCase().endsWith(".html") ? (
                      <iframe
                        className="coding-html-preview"
                        title={`Preview of ${editorPath}`}
                        sandbox=""
                        srcDoc={`<!doctype html><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:">${editorContent}`}
                      />
                    ) : (
                      <pre className="coding-text-preview">{editorContent || "No content to preview."}</pre>
                    )
                  ) : (
                    <textarea
                      className="coding-editor"
                      aria-label={`Edit ${editorPath}`}
                      value={editorContent}
                      onChange={event => setEditorContent(event.target.value)}
                      spellCheck={false}
                    />
                  )}
                  {(editorOriginal === null && editorContent.length > 0) ||
                  (editorOriginal !== null && editorContent !== editorOriginal) ? (
                    <small className="coding-editor-dirty">Unsaved changes — save is explicit and workspace-scoped.</small>
                  ) : null}
                </>
              ) : (
                <p className="coding-editor-empty">Choose Edit on a file, or create a new file to open the editor.</p>
              )}
            </section>

            {proposal && (
              <section className="coding-panel coding-proposal-panel" aria-live="polite">
                <div className="coding-panel-heading">
                  <div><span className="coding-panel-icon">⌘</span><div><h2>Review proposal</h2><p>{proposal.files.join(", ")} · {proposal.model}</p></div></div>
                  <span className={`coding-proposal-status ${proposal.applied ? "applied" : ""}`}>{proposal.status}</span>
                </div>
                <pre>{proposal.proposal}</pre>
                {!proposal.applied && proposal.status === "pending" && (
                  <div className="coding-proposal-actions">
                    <span>Review the patch before applying it to the workspace.</span>
                    <div>
                      <button type="button" className="coding-secondary" onClick={() => void decideProposal("reject")} disabled={busy}>Reject</button>
                      <button type="button" className="coding-primary" onClick={() => void decideProposal("apply")} disabled={busy}>Apply patch</button>
                    </div>
                  </div>
                )}
              </section>
            )}

            {activeSession && sessionMessages.length > 0 && (
              <section className="coding-panel coding-context-panel">
                <div className="coding-panel-heading">
                  <div><span className="coding-panel-icon">◷</span><div><h2>Session memory</h2><p>Saved prompts and proposals are reused as bounded context in follow-up tasks.</p></div></div>
                </div>
                <div className="coding-context-list">
                  {sessionMessages.map(message => (
                    <details key={message.id} open={message.role === "user"}>
                      <summary>{message.role === "user" ? "You" : "Agent"} · {new Date(message.created_at).toLocaleString()}</summary>
                      <pre>{message.content}</pre>
                    </details>
                  ))}
                </div>
              </section>
            )}

            <section className="coding-panel coding-permissions-panel" id="integrations">
              <div className="coding-panel-heading">
                <div><span className="coding-panel-icon">◈</span><div><h2>Permissions & integrations</h2><p>Workspace writes are isolated from command and external-tool execution.</p></div></div>
              </div>
              <div className="coding-permission-row">
                <div><strong>Manual review</strong><p>Every proposal waits for your explicit Apply or Reject decision.</p></div>
                <button type="button" className={`coding-mode-button ${permissions.mode === "manual" ? "selected" : ""}`} onClick={() => void updatePermissionMode("manual")} disabled={permissionBusy || permissions.mode === "manual"}>Use manual</button>
              </div>
              <div className="coding-permission-row">
                <div><strong>Auto-apply patches</strong><p>Automatically writes validated changes only inside this workspace. No shell or MCP/plugin calls.</p></div>
                <button type="button" className={`coding-mode-button ${permissions.mode === "auto" ? "selected auto" : ""}`} onClick={() => void updatePermissionMode("auto")} disabled={permissionBusy || permissions.mode === "auto"}>Enable auto</button>
              </div>
              <div className="coding-guardrails">
                <span>✓ Workspace paths only</span><span>✓ Stale files rejected</span><span>✓ Commands disabled</span><span>✓ External tools disabled</span>
              </div>
              {integrations && (
                <div className="coding-integrations-grid">
                  {([
                    ["Skills", integrations.skills],
                    ["Plugins", integrations.plugins],
                    ["MCP servers", integrations.mcp],
                  ] as const).map(([name, integration]) => (
                    <article className="coding-integration-card" key={name}>
                      <div><strong>{name}</strong><span className={integration.supported ? "integration-ready" : "integration-muted"}>{integration.connected.length ? `${integration.connected.length} connected` : "Not connected"}</span></div>
                      <p>{integration.status}</p>
                    </article>
                  ))}
                </div>
              )}
            </section>

            <section className="coding-panel coding-model-panel" id="models">
              <div className="coding-panel-heading">
                <div><span className="coding-panel-icon">◉</span><div><h2>Models & training</h2><p>Use a provider model already installed in your configured runtime.</p></div></div>
              </div>
              <div className="coding-model-summary">
                <div><span>Provider</span><strong>{models[0]?.provider || "Configured provider"}</strong></div>
                <div><span>Available models</span><strong>{models.length}</strong></div>
                <div><span>Training pipeline</span><strong>Not configured</strong></div>
              </div>
              <p className="coding-footnote">{integrations?.model_training.status || "Model training is not available in this deployment."} Custom model training, datasets, and evaluation need a dedicated training service.</p>
            </section>
          </div>
        ) : (
          <section className="coding-auth-card">
            <h2>Workspace unavailable</h2>
            <p>The coding workspace is not configured for this server.</p>
            <button type="button" className="coding-secondary" onClick={() => void loadWorkspace()}>Try again</button>
          </section>
        )}
      </main>
      </div>
      {settingsOpen && (
        <div
          className="coding-settings-backdrop"
          onMouseDown={event => {
            if (event.target === event.currentTarget) setSettingsOpen(false);
          }}
        >
          <section className="coding-settings-modal" role="dialog" aria-modal="true" aria-labelledby="coding-settings-title">
            <aside className="coding-settings-nav">
              <strong id="coding-settings-title">Settings</strong>
              <nav aria-label="Settings sections">
                {([
                  "General",
                  "Application",
                  "Appearance",
                  "Shortcuts",
                  "Notifications",
                  "Models",
                  "Browser",
                  "Projects",
                  "Conversations",
                  "Integrations",
                ] as const).map(section => (
                  <button
                    type="button"
                    key={section}
                    className={settingsSection === section ? "selected" : ""}
                    onClick={() => setSettingsSection(section)}
                  >
                    {section}
                  </button>
                ))}
              </nav>
              <div className="coding-settings-profile">
                <span>✦</span><div><strong>Administrator</strong><small>Workspace controls</small></div>
              </div>
            </aside>
            <div className="coding-settings-content">
              <header>
                <div>
                  <h2>{settingsSection}</h2>
                  <p>
                    {settingsSection === "General"
                      ? "Configure agent execution, permissions, and workspace behavior."
                      : `Review ${settingsSection.toLowerCase()} options for this deployment.`}
                  </p>
                </div>
                <button type="button" className="coding-settings-close" onClick={() => setSettingsOpen(false)} aria-label="Close settings">×</button>
              </header>

              {settingsSection === "General" && (
                <>
                  <h3>Interface layout</h3>
                  <div className="coding-layout-choices">
                    <article><span>▱</span><strong>Knowledge work</strong><p>General chat and research.</p></article>
                    <article className="selected"><span>⌘</span><strong>Software engineering</strong><p>Projects, files, sessions, and patch review.</p></article>
                  </div>
                  <h3>Global permissions</h3>
                  <p className="coding-settings-description">Controls how the coding agent can write to the configured workspace.</p>
                  <div className="coding-setting-list">
                    <div className="coding-setting-row">
                      <div><strong>Permission preset</strong><small>Choose whether validated patches require approval.</small></div>
                      <select
                        value={permissions?.mode || "manual"}
                        onChange={event => void updatePermissionMode(event.target.value as "manual" | "auto")}
                        disabled={!permissions || permissionBusy}
                        aria-label="Permission preset"
                      >
                        <option value="manual">Manual review</option>
                        <option value="auto">Auto-apply</option>
                      </select>
                    </div>
                    <div className="coding-setting-row"><div><strong>File permissions</strong><small>Only allowlisted text files inside the configured workspace.</small></div><span className="coding-setting-status">Workspace-scoped</span></div>
                    <div className="coding-setting-row"><div><strong>Terminal and external tools</strong><small>Shell, plugin, and MCP execution are not enabled.</small></div><span className="coding-setting-status disabled">Disabled</span></div>
                  </div>
                  <h3>Execution</h3>
                  <div className="coding-setting-note"><strong>Foreground tasks</strong><p>Tasks run when you submit them. Background queues, cancellation, and resumable runs are not configured.</p></div>
                </>
              )}
              {settingsSection === "Application" && (
                <div className="coding-setting-note"><strong>Local AI Agent workspace</strong><p>Project files stay under the configured workspace root. Sessions use the configured chat database. The API reports {available ? "workspace connected" : "workspace unavailable"}.</p></div>
              )}
              {settingsSection === "Appearance" && (
                <>
                  <h3>Theme</h3>
                  <div className="coding-layout-choices">
                    <article className="selected"><span>◐</span><strong>Dark</strong><p>The current workspace theme.</p></article>
                    <article className="disabled"><span>◯</span><strong>Light</strong><p>Not available yet.</p></article>
                  </div>
                </>
              )}
              {settingsSection === "Shortcuts" && (
                <div className="coding-setting-note"><strong>Keyboard shortcuts</strong><p>Custom shortcuts are not configured. Standard browser keyboard and accessibility controls remain available.</p></div>
              )}
              {settingsSection === "Notifications" && (
                <div className="coding-setting-note"><strong>Workspace notifications</strong><p>Task results and errors appear in the workspace. Email, push, and background-run notifications are not configured.</p></div>
              )}
              {settingsSection === "Models" && (
                <>
                  <h3>Available models</h3>
                  <p className="coding-settings-description">The selected model is used for new coding proposals.</p>
                  <div className="coding-model-choice-list">
                    {models.map(model => (
                      <button type="button" key={model.id} className={selectedModel === model.id ? "selected" : ""} onClick={() => setSelectedModel(model.id)}>
                        <span className="coding-model-radio">{selectedModel === model.id ? "●" : "○"}</span>
                        <span><strong>{model.name}</strong><small>{model.provider}{model.id === defaultModel ? " · Default" : ""}</small></span>
                      </button>
                    ))}
                    {!models.length && <p className="coding-empty">No models are available from the configured provider.</p>}
                  </div>
                  <div className="coding-setting-note"><strong>Model training</strong><p>{integrations?.model_training.status || "Custom training and evaluation are not configured."}</p></div>
                </>
              )}
              {settingsSection === "Browser" && (
                <div className="coding-setting-note"><strong>Web search</strong><p>Optional web search is available on the main chat route when a provider key is configured. The coding agent does not send project files to search.</p></div>
              )}
              {settingsSection === "Projects" && (
                <>
                  <h3>Workspace projects</h3>
                  <p className="coding-settings-description">Projects are the configured root and its direct child folders.</p>
                  <form className="coding-settings-create" onSubmit={event => void createProject(event)}>
                    <input aria-label="New project name in settings" value={projectName} maxLength={64} onChange={event => setProjectName(event.target.value)} placeholder="New project name" />
                    <button type="submit" className="coding-primary" disabled={!projectName.trim()}>Create project</button>
                  </form>
                  <div className="coding-settings-project-list">
                    {projects.map(project => (
                      <button type="button" className={selectedProject === project.id ? "selected" : ""} key={project.id} onClick={() => { void selectProject(project.id); setSettingsOpen(false); }}>
                        <span>▱</span><strong>{project.name}</strong>{selectedProject === project.id && <small>Current</small>}
                      </button>
                    ))}
                  </div>
                </>
              )}
              {settingsSection === "Conversations" && (
                <>
                  <h3>Project conversations</h3>
                  <p className="coding-settings-description">Saved sessions remain scoped to the selected project.</p>
                  <button type="button" className="coding-primary" onClick={() => { setSettingsOpen(false); void createSession(); }}>＋ New conversation</button>
                  <div className="coding-settings-project-list">
                    {sessions.map(session => (
                      <button type="button" className={activeSession?.id === session.id ? "selected" : ""} key={session.id} onClick={() => { setSettingsOpen(false); setActiveScreen("conversation"); void openSession(session.id); }}>
                        <span>◷</span><strong>{session.title}</strong><small>{new Date(session.updated_at).toLocaleDateString()}</small>
                      </button>
                    ))}
                    {!sessions.length && <p className="coding-empty">No saved conversations in this project.</p>}
                  </div>
                </>
              )}
              {settingsSection === "Integrations" && integrations && (
                <>
                  <h3>Connected services</h3>
                  <div className="coding-custom-grid">
                    {([
                      ["Skills", integrations.skills],
                      ["Plugins", integrations.plugins],
                      ["MCP servers", integrations.mcp],
                    ] as const).map(([name, integration]) => (
                      <article className="coding-custom-card" key={name}>
                        <div className="coding-custom-card-title"><h3>{name}</h3><span>{integration.connected.length ? `${integration.connected.length} connected` : "Not connected"}</span></div>
                        <p>{integration.status}</p>
                      </article>
                    ))}
                  </div>
                </>
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
