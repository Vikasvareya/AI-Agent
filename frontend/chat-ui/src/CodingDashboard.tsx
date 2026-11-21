import { FormEvent, KeyboardEvent as ReactKeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  Clock3,
  ChevronDown,
  ChevronRight,
  FileCode2,
  FileText,
  Folder,
  FolderOpen,
  Menu,
  MessageSquarePlus,
  Plus,
  RefreshCw,
  Search,
  Settings,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import {
  DEFAULT_APPEARANCE,
  useAppearance,
} from "./appearance";
import type { AppearancePreferences } from "./appearance";
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
type ApiCredential = {
  id: string;
  role: "admin" | "user";
  subject: string;
  expires_at: string;
  revoked_at: string | null;
  created_at: string;
  status: "active" | "expired" | "revoked";
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
type Project = {
  id: string;
  name: string;
  location?: string;
  external?: boolean;
};
type DirectoryListing = {
  current: string;
  parent: string | null;
  roots: string[];
  directories: Array<{ name: string; path: string }>;
};
type FileTreeNode = {
  name: string;
  path: string;
  kind: "directory" | "file";
  children: FileTreeNode[];
};
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
  | "Integrations"
  | "Credentials";
type AppMenu = "Workspace" | "View" | "Window";
function buildFileTree(files: string[], projectId: string): FileTreeNode[] {
  const root: FileTreeNode[] = [];
  for (const file of files) {
    const relativePath = projectId === "."
      ? file
      : file.startsWith(`${projectId}/`)
        ? file.slice(projectId.length + 1)
        : file;
    const parts = relativePath.split("/").filter(Boolean);
    let nodes = root;
    let path = "";
    parts.forEach((part, index) => {
      path = path ? `${path}/${part}` : part;
      const kind = index === parts.length - 1 ? "file" : "directory";
      let node = nodes.find(item => item.name === part && item.kind === kind);
      if (!node) {
        node = {
          name: part,
          path: kind === "file" ? file : path,
          kind,
          children: [],
        };
        nodes.push(node);
      }
      nodes = node.children;
    });
  }

  const sortNodes = (nodes: FileTreeNode[]) => {
    nodes.sort((first, second) =>
      first.kind === second.kind
        ? first.name.localeCompare(second.name)
        : first.kind === "directory" ? -1 : 1,
    );
    nodes.forEach(node => sortNodes(node.children));
  };
  sortNodes(root);
  return root;
}

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
  const { appearance, effectiveTheme } = useAppearance();
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
    <main
      className="coding-shared-page"
      data-theme={effectiveTheme}
      data-contrast={appearance.contrast}
      data-font={appearance.font}
      data-font-size={appearance.fontSize}
      data-density={appearance.density}
      data-reduce-motion={appearance.reduceMotion}
    >
      <header>
        <a href={`${import.meta.env.BASE_URL}coding/`}>
          AI Brain · Coding workspace
        </a>
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
  const [expandedProjectId, setExpandedProjectId] = useState(".");
  const [expandedDirectories, setExpandedDirectories] = useState<Set<string>>(
    () => new Set(),
  );
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [projectName, setProjectName] = useState("");
  const [projectParentPath, setProjectParentPath] = useState("");
  const [directoryPickerOpen, setDirectoryPickerOpen] = useState(false);
  const [directoryPickerPurpose, setDirectoryPickerPurpose] = useState<"create" | "import">("create");
  const [directoryListing, setDirectoryListing] = useState<DirectoryListing | null>(null);
  const [directoryPathDraft, setDirectoryPathDraft] = useState("");
  const [directoryBusy, setDirectoryBusy] = useState(false);
  const projectSwitchSequence = useRef(0);
  const sidebarSearchInput = useRef<HTMLInputElement>(null);
  const [sidebarSearch, setSidebarSearch] = useState("");
  const [projectContentLoading, setProjectContentLoading] = useState(false);
  const [workspaceDataError, setWorkspaceDataError] = useState(false);
  const [projectPickerOpen, setProjectPickerOpen] = useState(false);
  const [projectPickerSearch, setProjectPickerSearch] = useState("");
  const [projectPickerCreateOpen, setProjectPickerCreateOpen] = useState(false);
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
  const [credentials, setCredentials] = useState<ApiCredential[]>([]);
  const [credentialRole, setCredentialRole] = useState<"admin" | "user">("user");
  const [credentialSubject, setCredentialSubject] = useState("");
  const [credentialBusy, setCredentialBusy] = useState(false);
  const [credentialCreatedToken, setCredentialCreatedToken] = useState("");
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
  const { appearance, setAppearance, effectiveTheme } = useAppearance();
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

  useEffect(() => {
    const handleSearchShortcut = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        sidebarSearchInput.current?.focus();
      } else if (
        event.key === "Escape" &&
        document.activeElement === sidebarSearchInput.current
      ) {
        setSidebarSearch("");
        sidebarSearchInput.current?.blur();
      }
    };
    window.addEventListener("keydown", handleSearchShortcut);
    return () => window.removeEventListener("keydown", handleSearchShortcut);
  }, []);

  const sidebarSearchQuery = sidebarSearch.trim().toLowerCase();
  const sidebarFilteredFiles = useMemo(
    () => sidebarSearchQuery
      ? files.filter(file => file.toLowerCase().includes(sidebarSearchQuery))
      : files,
    [files, sidebarSearchQuery],
  );
  const sidebarFileTree = useMemo(
    () => buildFileTree(sidebarFilteredFiles, selectedProject),
    [sidebarFilteredFiles, selectedProject],
  );
  const fileTree = useMemo(
    () => buildFileTree(files, selectedProject),
    [files, selectedProject],
  );
  const projectDirectoryKeys = useMemo(() => {
    const keys: string[] = [];
    const collect = (nodes: FileTreeNode[]) => {
      for (const node of nodes) {
        if (node.kind === "directory") {
          keys.push(`${selectedProject}:${node.path}`);
          collect(node.children);
        }
      }
    };
    collect(fileTree);
    return keys;
  }, [fileTree, selectedProject]);
  const allProjectDirectoriesExpanded =
    projectDirectoryKeys.length > 0 &&
    projectDirectoryKeys.every(key => expandedDirectories.has(key));
  const sidebarFilteredProjects = useMemo(
    () => sidebarSearchQuery
      ? projects.filter(project =>
          project.name.toLowerCase().includes(sidebarSearchQuery) ||
          (project.id === selectedProject && sidebarFilteredFiles.length > 0),
        )
      : projects,
    [projects, selectedProject, sidebarFilteredFiles.length, sidebarSearchQuery],
  );
  const sidebarFilteredSessions = useMemo(
    () => sidebarSearchQuery
      ? sessions.filter(session => session.title.toLowerCase().includes(sidebarSearchQuery))
      : sessions,
    [sessions, sidebarSearchQuery],
  );
  const filteredFiles = useMemo(() => {
    const query = fileSearch.trim().toLowerCase();
    return query ? files.filter(file => file.toLowerCase().includes(query)) : files;
  }, [files, fileSearch]);
  const filteredFileTree = useMemo(
    () => buildFileTree(filteredFiles, selectedProject),
    [filteredFiles, selectedProject],
  );
  const filteredProjects = useMemo(() => {
    const query = projectPickerSearch.trim().toLowerCase();
    const matches = query
      ? projects.filter(project => project.name.toLowerCase().includes(query))
      : projects;
    return [...matches].sort((first, second) =>
      first.id === selectedProject ? -1
        : second.id === selectedProject ? 1
          : first.name.localeCompare(second.name),
    );
  }, [projects, projectPickerSearch, selectedProject]);
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

  async function loadCredentials(authToken = token) {
    const result = await request<{ credentials: ApiCredential[] }>(
      "/v1/auth/credentials",
      {},
      authToken,
    );
    setCredentials(result.credentials);
  }

  async function createCredential(event: FormEvent) {
    event.preventDefault();
    if (!credentialSubject.trim() || credentialBusy) return;
    setCredentialBusy(true);
    setError("");
    setSuccess("");
    setCredentialCreatedToken("");
    try {
      const result = await request<ApiCredential & { token: string }>(
        "/v1/auth/credentials",
        {
          method: "POST",
          body: JSON.stringify({
            role: credentialRole,
            subject: credentialSubject.trim(),
            ttl_seconds: 30 * 24 * 60 * 60,
          }),
        },
        token,
      );
      setCredentialCreatedToken(result.token);
      setCredentialSubject("");
      await loadCredentials();
      setSuccess("Credential created. Copy the one-time token now.");
    } catch (reason) {
      setError(messageOf(reason));
    } finally {
      setCredentialBusy(false);
    }
  }

  async function rotateCredential(credentialId: string) {
    if (!window.confirm("Rotate this credential? The current token will stop working immediately.")) {
      return;
    }
    setCredentialBusy(true);
    setError("");
    setSuccess("");
    setCredentialCreatedToken("");
    try {
      const result = await request<ApiCredential & { token: string }>(
        `/v1/auth/credentials/${encodeURIComponent(credentialId)}/rotate`,
        {
          method: "POST",
          body: JSON.stringify({ ttl_seconds: 30 * 24 * 60 * 60 }),
        },
        token,
      );
      setCredentialCreatedToken(result.token);
      await loadCredentials();
      setSuccess("Credential rotated. Copy the replacement token now.");
    } catch (reason) {
      setError(messageOf(reason));
    } finally {
      setCredentialBusy(false);
    }
  }

  async function revokeCredential(credentialId: string) {
    if (!window.confirm("Revoke this credential? It will stop working immediately.")) {
      return;
    }
    setCredentialBusy(true);
    setError("");
    setSuccess("");
    setCredentialCreatedToken("");
    try {
      await request(
        `/v1/auth/credentials/${encodeURIComponent(credentialId)}`,
        { method: "DELETE" },
        token,
      );
      await loadCredentials();
      setSuccess("Credential revoked.");
    } catch (reason) {
      setError(messageOf(reason));
    } finally {
      setCredentialBusy(false);
    }
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
    if (busy || loading) return;
    if (
      editorHasUnsavedChanges() &&
      !window.confirm("Discard unsaved editor changes and switch projects?")
    ) {
      return;
    }
    const sequence = ++projectSwitchSequence.current;
    setSelectedProject(projectId);
    setExpandedProjectId(projectId);
    setProjectContentLoading(true);
    setWorkspaceDataError(false);
    localStorage.setItem("coding-project", projectId);
    setFiles([]);
    setSessions([]);
    setSelectedFiles([]);
    setEditorPath("");
    setEditorContent("");
    setEditorOriginal(null);
    setProposal(null);
    setActiveSession(null);
    setSessionMessages([]);
    setShareUrl("");
    setError("");
    setSuccess("");
    try {
      const [fileResult, sessionResult] = await Promise.all([
        request<{ files: string[] }>(
          `/v1/coding/files?project=${encodeURIComponent(projectId)}`,
          {},
          token,
        ),
        request<{ sessions: CodingSessionSummary[] }>(
          `/v1/coding/sessions?project=${encodeURIComponent(projectId)}`,
          {},
          token,
        ),
      ]);
      if (sequence !== projectSwitchSequence.current) return;
      setFiles(fileResult.files);
      setSessions(sessionResult.sessions);
    } catch (reason) {
      if (sequence === projectSwitchSequence.current) {
        setWorkspaceDataError(true);
        setError(messageOf(reason));
      }
    } finally {
      if (sequence === projectSwitchSequence.current) {
        setProjectContentLoading(false);
      }
    }
  }

  async function createProject(event: FormEvent, parentPath?: string) {
    event.preventDefault();
    if (!projectName.trim() || busy || loading) return;
    setError("");
    try {
      const project = await request<Project>(
        "/v1/coding/projects",
        {
          method: "POST",
          body: JSON.stringify({
            name: projectName.trim(),
            parent_path: parentPath || undefined,
          }),
        },
        token,
      );
      setProjects(current => [
        ...current.filter(item => item.id === "."),
        ...[...current.filter(item => item.id !== "."), project]
          .sort((first, second) => first.name.localeCompare(second.name)),
      ]);
      setProjectName("");
      setProjectCreateOpen(false);
      setProjectPickerCreateOpen(false);
      await selectProject(project.id);
      setProjectPickerOpen(false);
      setProjectPickerSearch("");
      setSuccess(
        `Project "${project.name}" created in ${parentPath || "the configured workspace"}.`,
      );
    } catch (reason) {
      setError(messageOf(reason));
    }
  }

  async function loadDirectoryListing(path?: string) {
    setDirectoryBusy(true);
    setError("");
    try {
      const query = path ? `?path=${encodeURIComponent(path)}` : "";
      const result = await request<DirectoryListing>(
        `/v1/coding/directories${query}`,
        {},
        token,
      );
      setDirectoryListing(result);
      setDirectoryPathDraft(result.current);
    } catch (reason) {
      setError(messageOf(reason));
    } finally {
      setDirectoryBusy(false);
    }
  }

  function openDirectoryPicker(purpose: "create" | "import") {
    setDirectoryPickerPurpose(purpose);
    setDirectoryPickerOpen(true);
    setDirectoryListing(null);
    void loadDirectoryListing();
  }

  async function useSelectedDirectory() {
    if (!directoryListing) return;
    if (directoryPickerPurpose === "create") {
      setProjectParentPath(directoryListing.current);
      setDirectoryPickerOpen(false);
      return;
    }
    setBusy(true);
    setError("");
    try {
      const project = await request<Project>(
        "/v1/coding/projects/import",
        {
          method: "POST",
          body: JSON.stringify({ path: directoryListing.current }),
        },
        token,
      );
      setProjects(current => [
        ...current.filter(item => item.id === "."),
        ...[...current.filter(item => item.id !== "." && item.id !== project.id), project]
          .sort((first, second) => first.name.localeCompare(second.name)),
      ]);
      await selectProject(project.id);
      setDirectoryPickerOpen(false);
      setSuccess(`Project "${project.name}" added from ${directoryListing.current}.`);
    } catch (reason) {
      setError(messageOf(reason));
    } finally {
      setBusy(false);
    }
  }

  async function deleteProject(project: Project) {
    if (
      project.id === "." ||
      !window.confirm(
        project.external
          ? `Remove "${project.name}" from the workspace? Its files will stay at ${project.location}. Its saved conversations and pending proposals will be deleted.`
          : `Permanently delete "${project.name}", all files in its folder, saved conversations, and pending proposals? This cannot be undone.`,
      )
    ) {
      return;
    }
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      const result = await request<{
        deleted_conversations: number;
        files_deleted: boolean;
      }>(
        `/v1/coding/projects/${encodeURIComponent(project.id)}`,
        { method: "DELETE" },
        token,
      );
      setProjects(current => current.filter(item => item.id !== project.id));
      if (selectedProject === project.id) {
        setSelectedProject(".");
        setExpandedProjectId(".");
        localStorage.setItem("coding-project", ".");
        setFiles([]);
        setSessions([]);
        setActiveSession(null);
        setSessionMessages([]);
        setShareUrl("");
        setSelectedFiles([]);
        setProposal(null);
        setEditorPath("");
        setEditorContent("");
        setEditorOriginal(null);
        setTask("");
        await Promise.all([
          loadFiles(token, "."),
          loadSessions(token, "."),
        ]);
      }
      setSuccess(
        result.files_deleted
          ? `Project "${project.name}" and ${result.deleted_conversations} saved conversation(s) deleted.`
          : `Project "${project.name}" removed. Its files were kept; ${result.deleted_conversations} saved conversation(s) deleted.`,
      );
    } catch (reason) {
      setError(messageOf(reason));
    } finally {
      setBusy(false);
    }
  }

  async function deleteSession(session: CodingSessionSummary) {
    if (
      !window.confirm(
        `Delete "${session.title}" and its saved messages? Pending proposals will be discarded, and any share links will stop working.`,
      )
    ) {
      return;
    }
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await request(
        `/v1/coding/sessions/${encodeURIComponent(session.id)}`,
        { method: "DELETE" },
        token,
      );
      setSessions(current =>
        current.filter(item => item.id !== session.id),
      );
      if (activeSession?.id === session.id) {
        setActiveSession(null);
        setSessionMessages([]);
        setSelectedFiles([]);
        setTask("");
        setShareUrl("");
        setProposal(null);
      }
      setSuccess(`Conversation "${session.title}" deleted.`);
    } catch (reason) {
      setError(messageOf(reason));
    } finally {
      setBusy(false);
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
      setShareUrl(
        `${window.location.origin}${import.meta.env.BASE_URL}coding/share/${result.token}`,
      );
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
    setWorkspaceDataError(false);
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
      setExpandedProjectId(projectId);
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
        loadCredentials(authToken),
      ]);
    } catch (reason) {
      setWorkspaceDataError(true);
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
    if (!task.trim() || !activeSession || busy) return;
    if (selectedFiles.length === 0) {
      setFilePickerOpen(true);
      setError(
        "Select at least one workspace file to provide context before generating a proposal.",
      );
      return;
    }
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
    if (editorPath === file) return;
    if (
      editorHasUnsavedChanges() &&
      !window.confirm("Discard unsaved editor changes and open another file?")
    ) {
      return;
    }
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
      setActiveScreen("workspace");
    } catch (reason) {
      setError(messageOf(reason));
    }
  }

  function editorHasUnsavedChanges() {
    return editorOriginal === null
      ? editorContent.length > 0
      : editorContent !== editorOriginal;
  }

  function closeEditor() {
    if (
      editorHasUnsavedChanges() &&
      !window.confirm("Discard unsaved editor changes?")
    ) {
      return;
    }
    setEditorPath("");
    setEditorContent("");
    setEditorOriginal(null);
    setEditorPreview(false);
  }

  function startNewFile(event: FormEvent) {
    event.preventDefault();
    const name = newFileName.trim().replace(/\\/g, "/");
    if (!name) return;
    if (
      editorHasUnsavedChanges() &&
      !window.confirm("Discard unsaved editor changes and create another file?")
    ) {
      return;
    }
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
    setError("");
    setProposal(null);
  }

  function updateAppearance<K extends keyof AppearancePreferences>(
    key: K,
    value: AppearancePreferences[K],
  ) {
    setAppearance(current => ({ ...current, [key]: value }));
  }

  function toggleProject(projectId: string) {
    if (busy || loading) return;
    if (expandedProjectId === projectId) {
      setExpandedProjectId("");
    } else if (selectedProject === projectId) {
      setExpandedProjectId(projectId);
    } else {
      void selectProject(projectId);
    }
  }

  async function openProject(projectId: string) {
    await selectProject(projectId);
    setProjectPickerOpen(false);
    setProjectPickerSearch("");
  }

  function toggleDirectory(directory: string) {
    const key = `${selectedProject}:${directory}`;
    setExpandedDirectories(current => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function toggleAllDirectories() {
    if (!projectDirectoryKeys.length) return;
    setExpandedProjectId(selectedProject);
    setExpandedDirectories(current => {
      const next = new Set(current);
      const shouldExpand = projectDirectoryKeys.some(key => !current.has(key));
      for (const key of projectDirectoryKeys) {
        if (shouldExpand) next.add(key);
        else next.delete(key);
      }
      return next;
    });
  }

  function handleFileTreeKeyDown(event: ReactKeyboardEvent<HTMLElement>) {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    const item = target.closest<HTMLElement>("[data-tree-nav]");
    if (!item) return;

    const items = Array.from(
      event.currentTarget.querySelectorAll<HTMLElement>("[data-tree-nav]"),
    ).filter(treeItem => !treeItem.matches(":disabled"));
    const index = items.indexOf(item);
    if (index < 0) return;

    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const direction = event.key === "ArrowDown" ? 1 : -1;
      items[Math.max(0, Math.min(items.length - 1, index + direction))]?.focus();
    } else if (event.key === "Home" || event.key === "End") {
      event.preventDefault();
      items[event.key === "Home" ? 0 : items.length - 1]?.focus();
    } else if (
      event.key === "ArrowRight" &&
      item.dataset.treeKind === "directory"
    ) {
      event.preventDefault();
      const path = item.dataset.treePath || "";
      if (item.getAttribute("aria-expanded") !== "true") {
        toggleDirectory(path);
      } else {
        items.slice(index + 1).find(
          child => child.dataset.treeParent === path,
        )?.focus();
      }
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      if (
        item.dataset.treeKind === "directory" &&
        item.getAttribute("aria-expanded") === "true"
      ) {
        toggleDirectory(item.dataset.treePath || "");
      } else {
        const parentPath = item.dataset.treeParent;
        if (parentPath) {
          items.find(
            parent => parent.dataset.treePath === parentPath,
          )?.focus();
        }
      }
    }
  }

  function renderFileTree(nodes: FileTreeNode[], depth = 0, parentPath = "") {
    return nodes.map(node => {
      if (node.kind === "directory") {
        const key = `${selectedProject}:${node.path}`;
        const groupId = `sidebar-folder-${encodeURIComponent(key)}`;
        const expanded = expandedDirectories.has(key);
        return (
          <div className="coding-tree-node" key={key}>
            <button
              type="button"
              className="coding-file-tree-item directory"
              style={{ paddingLeft: 10 + depth * 12 }}
              data-tree-nav
              data-tree-kind="directory"
              data-tree-path={node.path}
              data-tree-parent={parentPath}
              data-tree-depth={depth}
              aria-expanded={expanded}
              aria-controls={groupId}
              onClick={() => toggleDirectory(node.path)}
              title={`${expanded ? "Collapse" : "Expand"} ${node.name}`}
            >
              <span className="coding-tree-caret" aria-hidden="true">
                {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
              </span>
              <span className="coding-tree-folder" aria-hidden="true">
                {expanded ? <FolderOpen size={13} /> : <Folder size={13} />}
              </span>
              <span className="coding-tree-name">{node.name}</span>
            </button>
            {expanded && (
              <div className="coding-file-tree-children" id={groupId} role="group">
                {renderFileTree(node.children, depth + 1, node.path)}
              </div>
            )}
          </div>
        );
      }
      return (
        <button
          type="button"
          className={`coding-file-tree-item file ${editorPath === node.path ? "selected" : ""}`}
          style={{ paddingLeft: 10 + depth * 12 }}
          data-tree-nav
          data-tree-kind="file"
          data-tree-parent={parentPath}
          data-tree-depth={depth}
          key={node.path}
          onClick={() => {
            setSidebarOpen(false);
            void openFile(node.path);
          }}
          title={`Open ${node.path}`}
        >
          <span className="coding-tree-caret" />
          <FileText className="coding-tree-file-icon" size={12} aria-hidden="true" />
          <span className="coding-tree-name">{node.name}</span>
        </button>
      );
    });
  }

  function renderWorkbenchFileTree(nodes: FileTreeNode[], depth = 0, parentPath = "") {
    return nodes.map(node => {
      if (node.kind === "directory") {
        const key = `${selectedProject}:${node.path}`;
        const groupId = `workbench-folder-${encodeURIComponent(key)}`;
        const expanded = expandedDirectories.has(key);
        return (
          <div className="coding-tree-node" key={key}>
            <button
              type="button"
              className="coding-file-row coding-folder-row"
              style={{ paddingLeft: 9 + depth * 14 }}
              data-tree-nav
              data-tree-kind="directory"
              data-tree-path={node.path}
              data-tree-parent={parentPath}
              data-tree-depth={depth}
              aria-expanded={expanded}
              aria-controls={groupId}
              onClick={() => toggleDirectory(node.path)}
            >
              <span className="coding-tree-caret" aria-hidden="true">
                {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
              </span>
              <span className="coding-file-glyph" aria-hidden="true">
                {expanded ? <FolderOpen size={13} /> : <Folder size={13} />}
              </span>
              <span className="coding-file-name">{node.name}</span>
            </button>
            {expanded && (
              <div className="coding-file-tree-children" id={groupId} role="group">
                {renderWorkbenchFileTree(node.children, depth + 1, node.path)}
              </div>
            )}
          </div>
        );
      }
      return (
        <div
          className="coding-file-row"
          key={node.path}
          style={{ paddingLeft: 9 + depth * 14 }}
        >
          <input
            type="checkbox"
            data-tree-nav
            data-tree-kind="file"
            data-tree-parent={parentPath}
            data-tree-depth={depth}
            aria-label={`Add ${node.path} to coding context`}
            checked={selectedFiles.includes(node.path)}
            disabled={!selectedFiles.includes(node.path) && selectedFiles.length >= 8}
            onChange={event => toggleFile(node.path, event.target.checked)}
          />
          <FileCode2 className="coding-file-glyph" size={12} aria-hidden="true" />
          <span className="coding-file-name">{node.name}</span>
          <button type="button" onClick={() => void openFile(node.path)}>Edit</button>
        </div>
      );
    });
  }

  return (
    <div
      className="coding-dashboard coding-app"
      data-theme={effectiveTheme}
      data-contrast={appearance.contrast}
      data-font={appearance.font}
      data-font-size={appearance.fontSize}
      data-density={appearance.density}
      data-reduce-motion={appearance.reduceMotion}
    >
      <header className="coding-appbar">
        <a className="coding-window-brand" href="/chat/" aria-label="AI Brain home">
          <span className="coding-brand-mark"><Sparkles size={16} aria-hidden="true" /></span>
          <strong>AI Brain</strong>
        </a>
        <button
          type="button"
          className="coding-sidebar-toggle"
          aria-label={sidebarOpen ? "Close workspace navigation" : "Open workspace navigation"}
          aria-expanded={sidebarOpen}
          onClick={() => setSidebarOpen(value => !value)}
        >
          {sidebarOpen ? <X size={17} aria-hidden="true" /> : <Menu size={17} aria-hidden="true" />}
        </button>
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
        {sidebarOpen && (
          <button
            type="button"
            className="coding-sidebar-backdrop"
            aria-label="Close workspace navigation"
            onClick={() => setSidebarOpen(false)}
          />
        )}
        <aside className={`coding-sidebar ${sidebarOpen ? "is-open" : ""}`}>
          <button
            type="button"
            className="coding-new-conversation"
            onClick={() => void createSession()}
            disabled={role !== "admin" || loading}
          >
            <MessageSquarePlus size={14} aria-hidden="true" /> New Conversation
          </button>
          <label className="coding-sidebar-search">
            <Search size={14} aria-hidden="true" />
            <input
              ref={sidebarSearchInput}
              type="search"
              aria-label="Search projects, files, and conversations"
              aria-keyshortcuts="Control+K Meta+K"
              title="Projects by name; files and conversations in the open project (Ctrl/⌘ K)"
              placeholder="Search workspace"
              value={sidebarSearch}
              onChange={event => setSidebarSearch(event.target.value)}
            />
            <kbd>Ctrl K</kbd>
          </label>
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
                  <div className="coding-tree-heading-actions">
                    <button
                      type="button"
                      className="coding-tree-expand-all"
                      title={allProjectDirectoriesExpanded ? "Collapse all folders" : "Expand all folders"}
                      aria-label={allProjectDirectoriesExpanded ? "Collapse all folders" : "Expand all folders"}
                      onClick={toggleAllDirectories}
                      disabled={busy || loading || projectContentLoading || !projectDirectoryKeys.length}
                    >
                      {allProjectDirectoriesExpanded
                        ? <ChevronDown size={13} aria-hidden="true" />
                        : <ChevronRight size={13} aria-hidden="true" />}
                    </button>
                    <button
                      type="button"
                      title="Create project"
                      aria-label="Create project"
                      onClick={() => setProjectCreateOpen(value => !value)}
                      disabled={busy || loading}
                    >
                      <Plus size={14} aria-hidden="true" />
                    </button>
                  </div>
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
                    <button type="submit" disabled={!projectName.trim() || busy || loading}>Add</button>
                  </form>
                )}
                <div className="coding-project-tree" role="group" aria-label="Workspace projects and files">
                  {loading || projectContentLoading ? (
                    <small className="coding-sidebar-empty" role="status">Loading projects and files…</small>
                  ) : workspaceDataError ? (
                    <small className="coding-sidebar-empty" role="status">Couldn’t load projects. See the error message above.</small>
                  ) : sidebarFilteredProjects.length ? sidebarFilteredProjects.map(project => {
                    const expanded = expandedProjectId === project.id;
                    return (
                      <div className="coding-project-node" key={project.id}>
                        <div className={`coding-project-row ${selectedProject === project.id ? "selected" : ""}`}>
                          <button
                            type="button"
                            className="coding-project-toggle"
                            aria-label={`${expanded ? "Collapse" : "Expand"} ${project.name}`}
                            aria-expanded={expanded}
                            onClick={() => toggleProject(project.id)}
                            disabled={busy || loading}
                          >
                            {expanded
                              ? <ChevronDown size={12} aria-hidden="true" />
                              : <ChevronRight size={12} aria-hidden="true" />}
                          </button>
                          <button
                            type="button"
                            className="coding-project-select"
                            aria-current={selectedProject === project.id ? "page" : undefined}
                            onClick={() => {
                              setSidebarOpen(false);
                              void selectProject(project.id);
                            }}
                            disabled={busy || loading}
                            title={`Open project ${project.name}`}
                          >
                            <span className="coding-tree-folder" aria-hidden="true">
                              {expanded ? <FolderOpen size={13} /> : <Folder size={13} />}
                            </span>
                            <span className="coding-tree-name">{project.name}</span>
                          </button>
                        </div>
                        {expanded && (
                          <div className="coding-project-files" role="group" aria-label={`${project.name} files`} onKeyDown={handleFileTreeKeyDown}>
                            {project.id === selectedProject ? (
                              sidebarSearchQuery && !sidebarFilteredFiles.length
                                ? <small className="coding-sidebar-empty">No files match in this project</small>
                                : sidebarSearchQuery
                                  ? sidebarFilteredFiles.map(file => (
                                      <button
                                        type="button"
                                        className={`coding-file-tree-item file ${editorPath === file ? "selected" : ""}`}
                                        key={file}
                                        data-tree-nav
                                        data-tree-kind="file"
                                        data-tree-depth={0}
                                        title={`Open ${file}`}
                                        onClick={() => {
                                          setSidebarOpen(false);
                                          void openFile(file);
                                        }}
                                      >
                                        <FileText className="coding-tree-file-icon" size={12} aria-hidden="true" />
                                        <span className="coding-tree-name">
                                          {selectedProject !== "." && file.startsWith(`${selectedProject}/`)
                                            ? file.slice(selectedProject.length + 1)
                                            : file}
                                        </span>
                                      </button>
                                    ))
                                : sidebarFileTree.length
                                  ? renderFileTree(sidebarFileTree)
                                  : <small className="coding-sidebar-empty">No eligible files in this project</small>
                            ) : (
                              <small className="coding-sidebar-empty">Open this project to browse its files</small>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  }) : (
                    <small className="coding-sidebar-empty">
                      {sidebarSearchQuery ? "No projects or files match." : "No projects available."}
                    </small>
                  )}
                </div>
              </section>
              <section className="coding-tree-section coding-conversation-tree">
                <div className="coding-tree-heading">
                  <span>Conversations</span>
                  <button type="button" title="New conversation" aria-label="New conversation" onClick={() => void createSession()}><Plus size={14} aria-hidden="true" /></button>
                </div>
                <div className="coding-session-list">
                  {loading || projectContentLoading ? (
                    <small className="coding-sidebar-empty" role="status">Loading conversations…</small>
                  ) : workspaceDataError ? (
                    <small className="coding-sidebar-empty" role="status">Couldn’t load conversations. See the error message above.</small>
                  ) : sidebarFilteredSessions.map(session => (
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
                  {!loading && !projectContentLoading && !workspaceDataError && !sidebarFilteredSessions.length && (
                    <small className="coding-sidebar-empty">
                      {sidebarSearchQuery
                        ? "No conversations match this search."
                        : "No conversations yet"}
                    </small>
                  )}
                </div>
              </section>
            </>
          )}
          <div className="coding-sidebar-bottom">
            <button type="button" className="coding-settings-trigger" onClick={() => { setSettingsSection("General"); setSettingsOpen(true); }}>
              <Settings size={14} aria-hidden="true" /> Settings
            </button>
            <div className="coding-admin-badge"><span /> {role === "admin" ? "Administrator" : "Workspace sign in required"}</div>
          </div>
        </aside>

      <main className="coding-main" id="overview">
        <header className="coding-topbar">
          <div className="coding-top-actions">
            <div className="coding-project-picker">
              <button
                type="button"
                className="coding-project-picker-trigger"
                aria-expanded={projectPickerOpen}
                aria-haspopup="dialog"
                onClick={() => {
                  setProjectPickerOpen(value => !value);
                  setProjectPickerSearch("");
                  setProjectPickerCreateOpen(false);
                }}
              >
                <Folder size={14} aria-hidden="true" />
                <span>{projects.find(project => project.id === selectedProject)?.name || "Workspace root"}</span>
                <ChevronDown size={13} aria-hidden="true" />
              </button>
              {projectPickerOpen && (
                <section
                  className="coding-project-picker-menu"
                  role="dialog"
                  aria-label="Choose a workspace project"
                >
                  <label className="coding-project-picker-search">
                    <Search size={14} aria-hidden="true" />
                    <input
                      type="search"
                      autoFocus
                      aria-label="Search projects"
                      placeholder="Search projects…"
                      value={projectPickerSearch}
                      onChange={event => setProjectPickerSearch(event.target.value)}
                    />
                  </label>
                  {projectPickerCreateOpen ? (
                    <form
                      className="coding-project-picker-create"
                      onSubmit={event => void createProject(event, projectParentPath || undefined)}
                    >
                      <strong>New project</strong>
                      <input
                        aria-label="New project name"
                        autoFocus
                        maxLength={64}
                        value={projectName}
                        onChange={event => setProjectName(event.target.value)}
                        placeholder="Project name"
                      />
                      <button
                        type="button"
                        className="coding-secondary"
                        disabled={busy || loading}
                        onClick={() => openDirectoryPicker("create")}
                      >
                        Choose location
                      </button>
                      <small>
                        Location: {projectParentPath || "configured workspace"}
                      </small>
                      <div>
                        <button
                          type="button"
                          className="coding-secondary"
                          onClick={() => {
                            setProjectPickerCreateOpen(false);
                            setProjectName("");
                          }}
                        >
                          Cancel
                        </button>
                        <button
                          type="submit"
                          className="coding-primary"
                          disabled={!projectName.trim() || busy || loading}
                        >
                          Create project
                        </button>
                      </div>
                    </form>
                  ) : (
                    <>
                      <div className="coding-project-picker-heading">
                        {projectPickerSearch ? "Search results" : "This workspace"}
                      </div>
                      <div className="coding-project-picker-list">
                        {filteredProjects.map(project => (
                          <button
                            type="button"
                            key={project.id}
                            className={selectedProject === project.id ? "selected" : ""}
                            title={project.location || project.name}
                            disabled={busy || loading}
                            onClick={() => void openProject(project.id)}
                          >
                            <Folder size={14} aria-hidden="true" />
                            <strong>{project.name}</strong>
                            {selectedProject === project.id && <span aria-label="Current project">✓</span>}
                          </button>
                        ))}
                        {!filteredProjects.length && (
                          <p className="coding-project-picker-empty">No projects match that search.</p>
                        )}
                      </div>
                      <button
                        type="button"
                        className="coding-project-picker-new"
                        disabled={busy || loading}
                        onClick={() => setProjectPickerCreateOpen(true)}
                      >
                        <Plus size={14} aria-hidden="true" /> New project
                      </button>
                      <p className="coding-project-picker-note">
                        Only folders inside the configured workspace are available.
                      </p>
                    </>
                  )}
                </section>
              )}
            </div>
            {activeSession && <span className="coding-location">{activeSession.title}</span>}
            <button type="button" className="coding-secondary" onClick={() => setActiveScreen("workspace")}>Workspace</button>
            {activeSession && (
              <>
                <button type="button" className="coding-secondary" onClick={() => void shareSession()} disabled={!sessionMessages.length}>Share</button>
                <button type="button" className="coding-secondary" onClick={() => void revokeSessionShares()} disabled={!activeSession}>Revoke</button>
              </>
            )}
            <button type="button" className="coding-refresh" onClick={() => void loadWorkspace()} disabled={loading}>
              {loading ? "Refreshing…" : <RefreshCw size={14} aria-hidden="true" />}
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
                      <span className="coding-message-avatar">
                        {message.role === "user" ? "You" : <Sparkles size={14} aria-hidden="true" />}
                      </span>
                      <div className="coding-message-body">
                        <strong>{message.role === "user" ? "You" : "AI Brain"}</strong>
                        <pre>{message.content}</pre>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="coding-conversation-welcome">
                  <div className="coding-welcome-symbol"><Sparkles size={24} aria-hidden="true" /></div>
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
                    <button type="button" onClick={() => setFilePickerOpen(false)} aria-label="Close file picker"><X size={14} aria-hidden="true" /></button>
                  </header>
                  <input
                    type="search"
                    className="coding-search"
                    value={fileSearch}
                    onChange={event => setFileSearch(event.target.value)}
                    placeholder="Search project files"
                    aria-label="Search project files"
                  />
                  <div className="coding-file-list" onKeyDown={handleFileTreeKeyDown}>
                    {filteredFiles.map(file => (
                      <label className="coding-file-option" key={file}>
                        <input
                          type="checkbox"
                          checked={selectedFiles.includes(file)}
                          disabled={!selectedFiles.includes(file) && selectedFiles.length >= 8}
                          onChange={event => toggleFile(file, event.target.checked)}
                        />
                        <FileText className="coding-file-glyph" size={12} aria-hidden="true" />
                        <span>{file}</span>
                      </label>
                    ))}
                    {!filteredFiles.length && <div className="coding-empty">No eligible files match this search.</div>}
                  </div>
                </section>
              )}
              <div className="coding-composer-context">
                <label>
                  <Folder size={13} aria-hidden="true" />
                  <select
                    id="coding-main-project"
                    value={selectedProject}
                    onChange={event => void selectProject(event.target.value)}
                    disabled={busy || loading}
                    aria-label="Current project"
                  >
                    {projects.map(project => <option value={project.id} key={project.id}>{project.name}</option>)}
                  </select>
                </label>
                <span className="coding-context-divider">/</span>
                <label>
                  <Clock3 size={13} aria-hidden="true" />
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
                      <Plus size={13} aria-hidden="true" /> <span>{selectedFiles.length ? `${selectedFiles.length} files` : "Add files"}</span>
                    </button>
                    <label className="coding-composer-select" aria-label="Task type">
                      <select value={taskKind} onChange={event => setTaskKind(event.target.value)}>
                        <option>Feature</option><option>Bug fix</option><option>Refactor</option><option>Tests</option><option>DSA problem</option>
                      </select>
                    </label>
                    <label className="coding-composer-select model" aria-label="Model">
                      <Sparkles size={13} aria-hidden="true" />
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
                        ◈ {permissions?.mode === "auto" ? "Auto" : "Manual"} <ChevronDown size={12} aria-hidden="true" />
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
                      aria-label={selectedFiles.length ? "Generate coding proposal" : "Select files to generate a proposal"}
                      disabled={!task.trim() || !activeSession || busy}
                      title={!selectedFiles.length ? "Select files to provide scoped context" : "Generate proposal"}
                    >
                      {busy ? "…" : "↑"}
                    </button>
                  </div>
                </div>
                <div className="coding-composer-footer">
                  <span>{selectedFiles.length ? `${selectedFiles.length} selected · only selected files are sent to the model` : "Send opens file selection; choose files to provide scoped context"}</span>
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
                <div className="coding-custom-art"><Sparkles size={19} aria-hidden="true" /></div>
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
                  <button type="submit" disabled={!projectName.trim() || busy || loading}>Create</button>
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
                  <div><span className="coding-panel-icon"><Sparkles size={15} aria-hidden="true" /></span><div><h2>Start a task</h2><p>Describe the outcome; the agent proposes a scoped patch.</p></div></div>
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
                  <div><FileText className="coding-panel-icon" size={15} aria-hidden="true" /><div><h2>Workspace files</h2><p>Choose the files the model can read and propose edits for.</p></div></div>
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
                <div className="coding-file-list" onKeyDown={handleFileTreeKeyDown}>
                  {filteredFileTree.length
                    ? renderWorkbenchFileTree(filteredFileTree)
                    : <div className="coding-empty">No eligible files match this search.</div>}
                </div>
                <p className="coding-footnote">Credentials, dependency folders, and generated files are excluded.</p>
              </section>
            </div>

            <section className="coding-panel coding-editor-panel">
              <div className="coding-panel-heading">
                <div><span className="coding-panel-icon">⌨</span><div><h2>Workspace editor</h2><p>Edit and save an explicit file; HTML preview blocks scripts.</p></div></div>
                {editorPath && (
                  <div className="coding-editor-heading-actions">
                    <span className="coding-count">{editorPath}</span>
                    <button
                      type="button"
                      className="coding-editor-close"
                      aria-label={`Close ${editorPath}`}
                      title="Close editor"
                      onClick={closeEditor}
                    >
                      <X size={13} aria-hidden="true" />
                    </button>
                  </div>
                )}
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
                  "Credentials",
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
                <span><Sparkles size={14} aria-hidden="true" /></span><div><strong>Administrator</strong><small>Workspace controls</small></div>
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
                <button type="button" className="coding-settings-close" onClick={() => setSettingsOpen(false)} aria-label="Close settings"><X size={15} aria-hidden="true" /></button>
              </header>

              {settingsSection === "General" && (
                <>
                  <h3>Interface layout</h3>
                  <div className="coding-layout-choices">
                    <article><Folder size={14} aria-hidden="true" /><strong>Knowledge work</strong><p>General chat and research.</p></article>
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
                <div className="coding-setting-note"><strong>Local AI Brain coding workspace</strong><p>Project files stay under the configured workspace root. Sessions use the configured chat database. The API reports {available ? "workspace connected" : "workspace unavailable"}.</p></div>
              )}
              {settingsSection === "Appearance" && (
                <>
                  <p className="coding-settings-description">
                    Personalize how the workspace looks. Changes are saved on this device.
                  </p>
                  <h3>Display</h3>
                  <div className="coding-setting-list coding-appearance-list">
                    <label className="coding-setting-row" htmlFor="appearance-theme">
                      <span><strong>Theme</strong><small>Choose dark, light, or follow your device.</small></span>
                      <select
                        id="appearance-theme"
                        value={appearance.theme}
                        onChange={event => updateAppearance("theme", event.target.value as AppearancePreferences["theme"])}
                      >
                        <option value="system">System</option>
                        <option value="dark">Dark</option>
                        <option value="light">Light</option>
                      </select>
                    </label>
                    <label className="coding-setting-row" htmlFor="appearance-contrast">
                      <span><strong>Contrast</strong><small>Increase borders and text clarity.</small></span>
                      <select
                        id="appearance-contrast"
                        value={appearance.contrast}
                        onChange={event => updateAppearance("contrast", event.target.value as AppearancePreferences["contrast"])}
                      >
                        <option value="default">Default</option>
                        <option value="high">High</option>
                      </select>
                    </label>
                    <label className="coding-setting-row" htmlFor="appearance-font">
                      <span><strong>Font</strong><small>Choose a comfortable interface typeface.</small></span>
                      <select
                        id="appearance-font"
                        value={appearance.font}
                        onChange={event => updateAppearance("font", event.target.value as AppearancePreferences["font"])}
                      >
                        <option value="dm-sans">DM Sans</option>
                        <option value="system">System</option>
                        <option value="mono">Monospace</option>
                      </select>
                    </label>
                    <label className="coding-setting-row" htmlFor="appearance-font-size">
                      <span><strong>Text size</strong><small>Adjust labels and conversation text.</small></span>
                      <select
                        id="appearance-font-size"
                        value={appearance.fontSize}
                        onChange={event => {
                          const size = Number(event.target.value);
                          if (size === 12 || size === 14 || size === 16 || size === 18) {
                            updateAppearance("fontSize", size);
                          }
                        }}
                      >
                        <option value={12}>Small · 12 px</option>
                        <option value={14}>Default · 14 px</option>
                        <option value={16}>Large · 16 px</option>
                        <option value={18}>Extra large · 18 px</option>
                      </select>
                    </label>
                    <label className="coding-setting-row" htmlFor="appearance-density">
                      <span><strong>Message spacing</strong><small>Choose more room or fit more in view.</small></span>
                      <select
                        id="appearance-density"
                        value={appearance.density}
                        onChange={event => updateAppearance("density", event.target.value as AppearancePreferences["density"])}
                      >
                        <option value="comfortable">Comfortable</option>
                        <option value="compact">Compact</option>
                      </select>
                    </label>
                    <label className="coding-setting-row coding-motion-row" htmlFor="appearance-reduced-motion">
                      <span><strong>Reduce motion</strong><small>Minimize transitions and animation.</small></span>
                      <input
                        id="appearance-reduced-motion"
                        type="checkbox"
                        checked={appearance.reduceMotion}
                        onChange={event => updateAppearance("reduceMotion", event.target.checked)}
                      />
                    </label>
                  </div>
                  <div className="coding-appearance-footer">
                    <span>Preferences apply immediately and stay saved between visits.</span>
                    <button
                      type="button"
                      className="coding-secondary"
                      onClick={() => setAppearance(DEFAULT_APPEARANCE)}
                      disabled={JSON.stringify(appearance) === JSON.stringify(DEFAULT_APPEARANCE)}
                    >
                      Reset to defaults
                    </button>
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
                  <p className="coding-settings-description">
                    Create projects in another server folder or add an existing project directory.
                  </p>
                  <div className="coding-project-location-actions">
                    <button
                      type="button"
                      className="coding-secondary"
                      disabled={busy || loading}
                      onClick={() => openDirectoryPicker("import")}
                    >
                      Add existing project
                    </button>
                  </div>
                  <form
                    className="coding-project-location-create"
                    onSubmit={event => void createProject(event, projectParentPath || undefined)}
                  >
                    <input
                      aria-label="New project name in settings"
                      value={projectName}
                      maxLength={64}
                      onChange={event => setProjectName(event.target.value)}
                      placeholder="New project name"
                    />
                    <div>
                      <button
                        type="button"
                        className="coding-secondary"
                        disabled={busy || loading}
                        onClick={() => openDirectoryPicker("create")}
                      >
                        Choose location
                      </button>
                      <button
                        type="submit"
                        className="coding-primary"
                        disabled={!projectName.trim() || busy || loading}
                      >
                        Create project
                      </button>
                    </div>
                    <small>
                      Location: {projectParentPath || "configured workspace"}
                    </small>
                  </form>
                  <div className="coding-settings-project-list">
                    {projects.map(project => (
                      <div className="coding-settings-project-row" key={project.id}>
                        <button
                          type="button"
                          className={`coding-settings-project-select ${selectedProject === project.id ? "selected" : ""}`}
                          title={project.location || project.name}
                          onClick={() => { void selectProject(project.id); setSettingsOpen(false); }}
                        >
                          <Folder size={14} aria-hidden="true" />
                          <span className="coding-project-setting-info">
                            <strong>{project.name}</strong>
                            {project.external && (
                              <small title={project.location}>{project.location}</small>
                            )}
                          </span>
                          <small>
                            {selectedProject === project.id
                              ? "Current"
                              : project.external
                                ? "External"
                                : ""}
                          </small>
                        </button>
                        {project.id !== "." && (
                          <button
                            type="button"
                            className="coding-delete-button"
                            aria-label={`Delete project ${project.name}`}
                            title={project.external
                              ? "Remove project from workspace; keep its files"
                              : "Permanently delete project and its conversations"}
                            disabled={busy || loading}
                            onClick={() => void deleteProject(project)}
                          >
                            <Trash2 size={14} aria-hidden="true" />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </>
              )}
              {settingsSection === "Conversations" && (
                <>
                  <h3>Project conversations</h3>
                  <p className="coding-settings-description">Saved sessions remain scoped to the selected project.</p>
                  <button type="button" className="coding-primary" onClick={() => { setSettingsOpen(false); void createSession(); }}><Plus size={14} aria-hidden="true" /> New conversation</button>
                  <div className="coding-settings-project-list">
                    {sessions.map(session => (
                      <div className="coding-settings-project-row" key={session.id}>
                        <button
                          type="button"
                          className={`coding-settings-project-select ${activeSession?.id === session.id ? "selected" : ""}`}
                          onClick={() => { setSettingsOpen(false); setActiveScreen("conversation"); void openSession(session.id); }}
                        >
                          <span>◷</span>
                          <strong>{session.title}</strong>
                          <small>{new Date(session.updated_at).toLocaleDateString()}</small>
                        </button>
                        <button
                          type="button"
                          className="coding-delete-button"
                          aria-label={`Delete conversation ${session.title}`}
                          title="Delete conversation and its saved messages"
                          disabled={busy || loading}
                          onClick={() => void deleteSession(session)}
                        >
                          <Trash2 size={14} aria-hidden="true" />
                        </button>
                      </div>
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
              {settingsSection === "Credentials" && (
                <>
                  <h3>API credentials</h3>
                  <p className="coding-settings-description">
                    Create and manage expiring bearer credentials. Raw tokens are shown only once.
                  </p>
                  {credentialCreatedToken && (
                    <div className="coding-credential-token">
                      <div><strong>New bearer token</strong><small>Copy and store this securely now.</small></div>
                      <input readOnly value={credentialCreatedToken} aria-label="New bearer token" />
                      <button
                        type="button"
                        className="coding-secondary"
                        onClick={() => void navigator.clipboard.writeText(credentialCreatedToken)}
                      >
                        Copy
                      </button>
                    </div>
                  )}
                  <form className="coding-credential-create" onSubmit={event => void createCredential(event)}>
                    <input
                      aria-label="Credential subject"
                      value={credentialSubject}
                      maxLength={128}
                      onChange={event => setCredentialSubject(event.target.value)}
                      placeholder="Subject, for example tenant-a:alice"
                    />
                    <select
                      aria-label="Credential role"
                      value={credentialRole}
                      onChange={event => setCredentialRole(event.target.value as "admin" | "user")}
                    >
                      <option value="user">User</option>
                      <option value="admin">Administrator</option>
                    </select>
                    <button type="submit" className="coding-primary" disabled={!credentialSubject.trim() || credentialBusy}>
                      Create
                    </button>
                  </form>
                  <div className="coding-credential-list">
                    {credentials.map(credential => (
                      <article key={credential.id}>
                        <div>
                          <strong>{credential.subject}</strong>
                          <small>{credential.role} · {credential.status} · expires {new Date(credential.expires_at).toLocaleString()}</small>
                        </div>
                        {credential.status === "active" ? (
                          <div className="coding-credential-actions">
                            <button type="button" className="coding-secondary" disabled={credentialBusy} onClick={() => void rotateCredential(credential.id)}>
                              Rotate
                            </button>
                            <button type="button" className="coding-secondary" disabled={credentialBusy} onClick={() => void revokeCredential(credential.id)}>
                              Revoke
                            </button>
                          </div>
                        ) : (
                          <span className="coding-setting-status disabled">{credential.status}</span>
                        )}
                      </article>
                    ))}
                    {!credentials.length && <p className="coding-empty">No API credentials have been created.</p>}
                  </div>
                </>
              )}
            </div>
          </section>
        </div>
      )}
      {directoryPickerOpen && (
        <div className="coding-directory-overlay">
          <section
            className="coding-directory-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="coding-directory-title"
          >
            <header>
              <div>
                <h2 id="coding-directory-title">
                  {directoryPickerPurpose === "create"
                    ? "Choose project location"
                    : "Add existing project"}
                </h2>
                <p>Select a folder on the computer running the AI Brain server.</p>
              </div>
              <button
                type="button"
                className="coding-settings-close"
                aria-label="Close directory picker"
                onClick={() => setDirectoryPickerOpen(false)}
              >
                <X size={15} aria-hidden="true" />
              </button>
            </header>
            <form
              className="coding-directory-path"
              onSubmit={event => {
                event.preventDefault();
                void loadDirectoryListing(directoryPathDraft);
              }}
            >
              <input
                aria-label="Directory path"
                value={directoryPathDraft}
                onChange={event => setDirectoryPathDraft(event.target.value)}
                placeholder="Absolute directory path"
              />
              <button type="submit" className="coding-secondary" disabled={directoryBusy}>
                Go
              </button>
            </form>
            {error && <p className="coding-directory-error" role="alert">{error}</p>}
            <div className="coding-directory-current" title={directoryListing?.current || ""}>
              {directoryListing?.current || "Loading locations…"}
            </div>
            <div className="coding-directory-list" aria-label="Available directories">
              {directoryBusy && <p className="coding-empty">Loading folders…</p>}
              {!directoryBusy && directoryListing && (
                <>
                  {directoryListing.parent && (
                    <button
                      type="button"
                      onClick={() => void loadDirectoryListing(directoryListing.parent || undefined)}
                    >
                      <FolderOpen size={14} aria-hidden="true" />
                      <span>..</span>
                      <small>Parent folder</small>
                    </button>
                  )}
                  {directoryListing.roots
                    .filter(root => root.toLowerCase() !== directoryListing.current.toLowerCase())
                    .map(root => (
                      <button type="button" key={root} onClick={() => void loadDirectoryListing(root)}>
                        <Folder size={14} aria-hidden="true" />
                        <span>{root}</span>
                        <small>Drive</small>
                      </button>
                    ))}
                  {directoryListing.directories.map(directory => (
                    <button
                      type="button"
                      key={directory.path}
                      title={directory.path}
                      onClick={() => void loadDirectoryListing(directory.path)}
                    >
                      <Folder size={14} aria-hidden="true" />
                      <span>{directory.name}</span>
                    </button>
                  ))}
                  {!directoryListing.parent &&
                    !directoryListing.roots.length &&
                    !directoryListing.directories.length && (
                      <p className="coding-empty">No folders are available here.</p>
                    )}
                </>
              )}
            </div>
            <footer>
              <button
                type="button"
                className="coding-secondary"
                onClick={() => setDirectoryPickerOpen(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="coding-primary"
                disabled={!directoryListing || directoryBusy || busy}
                onClick={() => void useSelectedDirectory()}
              >
                {directoryPickerPurpose === "create" ? "Use this location" : "Add this project"}
              </button>
            </footer>
          </section>
        </div>
      )}
    </div>
  );
}
