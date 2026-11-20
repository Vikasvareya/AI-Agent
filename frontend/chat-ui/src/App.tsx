import {
  FormEvent,
  KeyboardEvent,
  MouseEvent,
  useEffect,
  useRef,
  useState,
} from "react";
import CodingDashboard, { SharedCodingSession } from "./CodingDashboard";

type Role = "user" | "assistant";
type Session = "guest" | "user" | "admin";
type ChatMode = "chat" | "coding";
type ModelOption = {
  id: string;
  name: string;
  provider: string;
};
type Capability = {
  id: string;
  available: boolean;
  reason?: string;
};
type CodingProposal = {
  proposal: string;
  files: string[];
  model: string;
  applied: boolean;
};
type Conversation = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
};
type Message = {
  id: string;
  role: Role;
  content: string;
  created_at: string;
};

class ApiError extends Error {
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
    throw new ApiError(
      data.message || `Request failed (${response.status}).`,
      response.status,
    );
  }
  return data as T;
}

export default function App() {
  const path = window.location.pathname;
  const sharedSession = path.match(/^\/coding\/share\/([A-Za-z0-9_-]+)\/?$/);
  if (sharedSession) {
    return <SharedCodingSession token={sharedSession[1]} />;
  }
  if (path === "/coding" || path.startsWith("/coding/")) {
    return <CodingDashboard />;
  }
  return <ChatApp />;
}

function ChatApp() {
  const [session, setSession] = useState<Session>("guest");
  const [token, setToken] = useState("");
  const [tokenDraft, setTokenDraft] = useState("");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [models, setModels] = useState<ModelOption[]>([]);
  const [defaultModel, setDefaultModel] = useState("");
  const [selectedModel, setSelectedModel] = useState("");
  const [modelLoading, setModelLoading] = useState(true);
  const [modelError, setModelError] = useState("");
  const [capabilities, setCapabilities] = useState<Record<string, Capability>>({});
  const [webSearchEnabled, setWebSearchEnabled] = useState(false);
  const [webSearchQuery, setWebSearchQuery] = useState("");
  const [mode, setMode] = useState<ChatMode>("chat");
  const [codingAgentAvailable, setCodingAgentAvailable] = useState(false);
  const [codingAgentReason, setCodingAgentReason] = useState("Administrator access and a coding workspace are required.");
  const [codingAgentOpen, setCodingAgentOpen] = useState(false);
  const [codingFiles, setCodingFiles] = useState<string[]>([]);
  const [codingFilesTruncated, setCodingFilesTruncated] = useState(false);
  const [codingFilesLoading, setCodingFilesLoading] = useState(false);
  const [codingFilesError, setCodingFilesError] = useState("");
  const [codingFileSearch, setCodingFileSearch] = useState("");
  const [codingSelectedFiles, setCodingSelectedFiles] = useState<string[]>([]);
  const [codingTask, setCodingTask] = useState("");
  const [codingProposal, setCodingProposal] = useState<CodingProposal | null>(null);
  const [codingSubmitting, setCodingSubmitting] = useState(false);
  const [codingAgentError, setCodingAgentError] = useState("");
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [accountOpen, setAccountOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    void initialize();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  async function initialize() {
    const savedToken = sessionStorage.getItem("agent-token") || "";
    if (savedToken) {
      try {
        const account = await request<{ role: Session }>(
          "/v1/session",
          {},
          savedToken,
        );
        setToken(savedToken);
        setSession(account.role);
        await refreshConversations(savedToken, true);
        await refreshModels(savedToken);
        await refreshCapabilities(savedToken);
        await refreshCodingStatus(savedToken);
        setLoading(false);
        return;
      } catch {
        sessionStorage.removeItem("agent-token");
      }
    }
    try {
      await request("/v1/chat/guest-sessions", { method: "POST" });
      setSession("guest");
      await refreshConversations("", true);
      await refreshModels("");
      await refreshCapabilities("");
      await refreshCodingStatus("");
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setLoading(false);
    }
  }

  async function refreshModels(authToken = token, forceRefresh = false) {
    setModelLoading(true);
    setModelError("");
    try {
      const catalog = await request<{
        default_model: string;
        models: ModelOption[];
      }>(
        `/v1/chat/models${forceRefresh ? "?refresh=true" : ""}`,
        {},
        authToken,
      );
      const savedModel = localStorage.getItem("agent-model-id") || "";
      const nextModel = catalog.models.some(model => model.id === savedModel)
        ? savedModel
        : "";
      setModels(catalog.models);
      setDefaultModel(catalog.default_model);
      setSelectedModel(nextModel);
      if (nextModel) localStorage.setItem("agent-model-id", nextModel);
      else localStorage.removeItem("agent-model-id");
    } catch (reason) {
      setModelError(errorMessage(reason));
      setModels([]);
    } finally {
      setModelLoading(false);
    }
  }

  async function refreshCapabilities(authToken = token) {
    try {
      const result = await request<{ modes: Capability[] }>(
        "/v1/chat/capabilities",
        {},
        authToken,
      );
      setCapabilities(
        Object.fromEntries(result.modes.map(capability => [capability.id, capability])),
      );
    } catch (reason) {
      setError(errorMessage(reason));
    }
  }

  async function refreshCodingStatus(authToken = token) {
    try {
      const status = await request<{
        available: boolean;
        reason?: string | null;
      }>(
        "/v1/coding/status",
        {},
        authToken,
      );
      setCodingAgentAvailable(status.available);
      setCodingAgentReason(
        status.available
          ? ""
          : status.reason || "Only administrators can use the project coding agent.",
      );
    } catch (reason) {
      setCodingAgentAvailable(false);
      setCodingAgentReason(errorMessage(reason));
    }
  }

  async function openCodingAgent() {
    if (!codingAgentAvailable) return;
    setCodingAgentOpen(true);
    setCodingAgentError("");
    setCodingProposal(null);
    setCodingFilesError("");
    if (codingFiles.length > 0) return;

    setCodingFilesLoading(true);
    try {
      const result = await request<{ files: string[]; truncated: boolean }>(
        "/v1/coding/files",
        {},
        token,
      );
      setCodingFiles(result.files);
      setCodingFilesTruncated(result.truncated);
    } catch (reason) {
      setCodingFilesError(errorMessage(reason));
    } finally {
      setCodingFilesLoading(false);
    }
  }

  async function proposeCodingChange(event: FormEvent) {
    event.preventDefault();
    if (!codingTask.trim() || codingSelectedFiles.length === 0 || codingSubmitting) {
      return;
    }
    setCodingAgentError("");
    setCodingProposal(null);
    setCodingSubmitting(true);
    try {
      const result = await request<CodingProposal>(
        "/v1/coding/proposals",
        {
          method: "POST",
          body: JSON.stringify({
            task: codingTask.trim(),
            files: codingSelectedFiles,
            model: selectedModel || undefined,
          }),
        },
        token,
      );
      setCodingProposal(result);
    } catch (reason) {
      setCodingAgentError(errorMessage(reason));
    } finally {
      setCodingSubmitting(false);
    }
  }

  async function refreshConversations(
    authToken = token,
    forceOpenFirst = false,
  ) {
    const result = await request<{ conversations: Conversation[] }>(
      "/v1/chat/conversations",
      {},
      authToken,
    );
    setConversations(result.conversations);
    if (
      !forceOpenFirst &&
      selectedId &&
      result.conversations.some(item => item.id === selectedId)
    ) {
      return;
    }
    if (result.conversations.length > 0) {
      await openConversation(result.conversations[0].id, authToken);
    } else {
      setSelectedId("");
      setMessages([]);
    }
  }

  async function openConversation(id: string, authToken = token) {
    setError("");
    try {
      const conversation = await request<Conversation & { messages: Message[] }>(
        `/v1/chat/conversations/${encodeURIComponent(id)}`,
        {},
        authToken,
      );
      setSelectedId(conversation.id);
      setMessages(conversation.messages);
      setSidebarOpen(false);
    } catch (reason) {
      setError(errorMessage(reason));
    }
  }

  async function createConversation() {
    setError("");
    try {
      const conversation = await request<Conversation>(
        "/v1/chat/conversations",
        {
          method: "POST",
          body: JSON.stringify({ title: "New chat" }),
        },
        token,
      );
      setConversations(current => [conversation, ...current]);
      setSelectedId(conversation.id);
      setMessages([]);
      setSidebarOpen(false);
      inputRef.current?.focus();
    } catch (reason) {
      setError(errorMessage(reason));
    }
  }

  async function sendMessage(event?: FormEvent) {
    event?.preventDefault();
    const content = input.trim();
    if (!content || sending) return;
    if (webSearchEnabled && !webSearchQuery.trim()) {
      setError("Enter separate search terms before sending with web search.");
      return;
    }
    if (content.length > 8000) {
      setError("Messages are limited to 8,000 characters.");
      return;
    }
    setError("");
    setSending(true);
    setInput("");
    const clientMessageId = crypto.randomUUID();
    const optimisticMessage: Message = {
      id: clientMessageId,
      role: "user",
      content,
      created_at: new Date().toISOString(),
    };
    setMessages(current => [...current, optimisticMessage]);

    try {
      let conversationId = selectedId;
      if (!conversationId) {
        const conversation = await request<Conversation>(
          "/v1/chat/conversations",
          {
            method: "POST",
            body: JSON.stringify({ title: "New chat" }),
          },
          token,
        );
        conversationId = conversation.id;
        setSelectedId(conversationId);
        setConversations(current => [conversation, ...current]);
      }
      const result = await request<{
        user_message: Message;
        assistant_message: Message;
      }>(
        `/v1/chat/conversations/${encodeURIComponent(conversationId)}/messages`,
        {
          method: "POST",
          body: JSON.stringify({
            content,
            client_message_id: clientMessageId,
            model: selectedModel || undefined,
            mode,
            web_search: webSearchEnabled,
            search_query: webSearchEnabled ? webSearchQuery.trim() : undefined,
          }),
        },
        token,
      );
      setMessages(current => [
        ...current.filter(message => message.id !== clientMessageId),
        result.user_message,
        result.assistant_message,
      ]);
      await refreshConversations();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  }

  function onComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage();
    }
  }

  async function signIn(event: FormEvent) {
    event.preventDefault();
    const candidate = tokenDraft.trim();
    if (!candidate) return;
    setError("");
    try {
      const account = await request<{ role: Session }>(
        "/v1/session",
        {},
        candidate,
      );
      setToken(candidate);
      sessionStorage.setItem("agent-token", candidate);
      setSession(account.role);
      setTokenDraft("");
      setAccountOpen(false);
      setSelectedId("");
      await refreshConversations(candidate, true);
      await refreshModels(candidate);
      await refreshCapabilities(candidate);
      await refreshCodingStatus(candidate);
    } catch (reason) {
      setError(errorMessage(reason));
    }
  }

  async function continueAsGuest() {
    setError("");
    sessionStorage.removeItem("agent-token");
    setToken("");
    try {
      await request("/v1/chat/guest-sessions", { method: "POST" });
      setSession("guest");
      setSelectedId("");
      setConversations([]);
      setMessages([]);
      setAccountOpen(false);
      await refreshConversations("", true);
      await refreshModels("");
      await refreshCapabilities("");
      await refreshCodingStatus("");
      setCodingFiles([]);
      setCodingSelectedFiles([]);
    } catch (reason) {
      setError(errorMessage(reason));
    }
  }

  async function deleteConversation(
    event: MouseEvent<HTMLButtonElement>,
    id: string,
  ) {
    event.stopPropagation();
    setError("");
    try {
      await request(
        `/v1/chat/conversations/${encodeURIComponent(id)}`,
        { method: "DELETE" },
        token,
      );
      const remaining = conversations.filter(item => item.id !== id);
      setConversations(remaining);
      if (selectedId === id) {
        setSelectedId("");
        setMessages([]);
        if (remaining[0]) await openConversation(remaining[0].id);
      }
    } catch (reason) {
      setError(errorMessage(reason));
    }
  }

  return (
    <div className="app-shell">
      {sidebarOpen && (
        <button
          className="sidebar-scrim"
          aria-label="Close conversation menu"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="brand">
          <div className="brand-mark">✦</div>
          <div>
            <strong>Agent</strong>
            <span>Workspace</span>
          </div>
          <a className="control-link" href="/" title="Open workflow control plane">
            ↗
          </a>
        </div>
        <button className="new-chat" onClick={() => void createConversation()}>
          <span>＋</span> New chat
        </button>
        <div className="history-label">YOUR CHATS</div>
        <nav className="conversation-list" aria-label="Conversations">
          {conversations.map(conversation => (
            <div className="conversation-row" key={conversation.id}>
              <button
                className={`conversation-item ${selectedId === conversation.id ? "selected" : ""}`}
                onClick={() => void openConversation(conversation.id)}
                title={conversation.title}
              >
                <span className="conversation-title">{conversation.title}</span>
              </button>
              <button
                className="delete-chat"
                aria-label={`Delete ${conversation.title}`}
                title="Delete chat"
                onClick={event => void deleteConversation(event, conversation.id)}
              >
                ×
              </button>
            </div>
          ))}
          {!loading && conversations.length === 0 && (
            <p className="sidebar-empty">Your conversations will appear here.</p>
          )}
        </nav>
        <div className="sidebar-bottom">
          <button className="account-button" onClick={() => setAccountOpen(true)}>
            <span className="avatar">{session === "guest" ? "G" : "U"}</span>
            <span className="account-copy">
              <strong>{session === "guest" ? "Guest session" : `${session} account`}</strong>
              <small>{session === "guest" ? "Temporary chat history" : "Signed in"}</small>
            </span>
            <span className="account-menu">•••</span>
          </button>
        </div>
      </aside>

      <main className="chat-main">
        <header className="topbar">
          <button
            className="mobile-menu"
            aria-label="Open conversation menu"
            onClick={() => setSidebarOpen(true)}
          >
            ☰
          </button>
          <div className="model-label">
            <span className="status-dot" /> AI Agent <span className="chevron">⌄</span>
          </div>
          <div className="top-actions">
            <a className="coding-workspace-link" href="/coding/">
              Coding workspace
            </a>
            <button
              className="coding-agent-link"
              title={codingAgentReason}
              disabled={!codingAgentAvailable}
              onClick={() => void openCodingAgent()}
            >
              Coding Agent
            </button>
            <a href="/" className="workflow-link">Workflow console</a>
            <button className="mobile-account" onClick={() => setAccountOpen(true)}>
              {session === "guest" ? "Guest" : session}
            </button>
          </div>
        </header>

        {error && (
          <div className="error-banner" role="alert">
            <span>{error}</span>
            <button aria-label="Dismiss error" onClick={() => setError("")}>×</button>
          </div>
        )}

        <section className="conversation-stage" aria-live="polite">
          {loading ? (
            <div className="welcome loading-state">
              <div className="loader" /> Connecting to your chat...
            </div>
          ) : messages.length === 0 ? (
            <div className="welcome">
              <div className="welcome-symbol">✦</div>
              <p className="eyebrow">YOUR AI WORKSPACE</p>
              <h1>What can I help with?</h1>
              <p className="welcome-note">Ask a question, explore an idea, or start with one of these.</p>
              <div className="suggestions">
                <button onClick={() => setInput("Explain a complex topic in simple terms")}>
                  <span>✧</span><strong>Learn something</strong><small>Break down any topic</small>
                </button>
                <button onClick={() => setInput("Help me brainstorm ideas for a project")}>
                  <span>⌘</span><strong>Explore an idea</strong><small>Think through a challenge</small>
                </button>
                <button onClick={() => setInput("Help me write a clear, professional message")}>
                  <span>✎</span><strong>Write something</strong><small>Draft, edit, or improve text</small>
                </button>
              </div>
            </div>
          ) : (
            <div className="message-list">
              {messages.map(message => (
                <article className={`message ${message.role}`} key={message.id}>
                  <div className={`message-avatar ${message.role}`}>
                    {message.role === "assistant" ? "✦" : "Y"}
                  </div>
                  <div className="message-content">
                    <div className="message-author">
                      {message.role === "assistant" ? "AI Agent" : "You"}
                    </div>
                    <div className="message-text">{renderMessageContent(message.content)}</div>
                  </div>
                </article>
              ))}
              {sending && (
                <article className="message assistant">
                  <div className="message-avatar assistant">✦</div>
                  <div className="message-content">
                    <div className="message-author">AI Agent</div>
                    <div className="thinking"><i /><i /><i /></div>
                  </div>
                </article>
              )}
              <div ref={bottomRef} />
            </div>
          )}
        </section>

        <footer className="composer-wrap">
          <form className="composer" onSubmit={event => void sendMessage(event)}>
            <div className="composer-tools">
              <div className="mode-options" role="group" aria-label="Assistant mode">
                <button
                  type="button"
                  className={`mode-option ${mode === "chat" ? "active" : ""}`}
                  onClick={() => setMode("chat")}
                >
                  <span>◉</span> Chat
                </button>
                <button
                  type="button"
                  className={`mode-option ${mode === "coding" ? "active" : ""}`}
                  disabled={!capabilities.coding?.available}
                  onClick={() => setMode("coding")}
                >
                  <span>{"</>"}</span> Coding
                </button>
                <span
                  className="unavailable-mode"
                  title={capabilities.image?.reason || "No image provider is configured."}
                >
                  <button type="button" className="mode-option" disabled>
                    <span>▧</span> Image
                  </button>
                  <small>Not configured</small>
                </span>
                <span
                  className="unavailable-mode"
                  title={capabilities.video?.reason || "No video provider is configured."}
                >
                  <button type="button" className="mode-option" disabled>
                    <span>▶</span> Video
                  </button>
                  <small>Not configured</small>
                </span>
              </div>
              <div className="model-control">
                <label htmlFor="model-select">
                  <span>Model{models.length ? ` · ${models.length} available` : ""}</span>
                  <select
                    id="model-select"
                    aria-label="Choose model"
                    value={selectedModel}
                    disabled={modelLoading}
                    onChange={event => {
                      setSelectedModel(event.target.value);
                      if (event.target.value) {
                        localStorage.setItem("agent-model-id", event.target.value);
                      } else {
                        localStorage.removeItem("agent-model-id");
                      }
                    }}
                  >
                    <option value="">
                      Provider default{defaultModel ? ` · ${defaultModel}` : ""}
                    </option>
                    {models.map(model => (
                      <option key={model.id} value={model.id}>
                        {model.name} · {model.provider}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  className="refresh-models"
                  aria-label="Refresh model list"
                  title="Refresh model list"
                  disabled={modelLoading}
                  onClick={() => void refreshModels(token, true)}
                >
                  {modelLoading ? "…" : "↻"}
                </button>
              </div>
            </div>
            <label
              className="web-search-toggle"
              title={capabilities.web_search?.available
                ? "Only separate terms are sent to Brave Search; common secret and code patterns are rejected."
                : capabilities.web_search?.reason || "Web search is not configured."}
            >
              <input
                type="checkbox"
                checked={webSearchEnabled}
                disabled={!capabilities.web_search?.available || sending}
                onChange={event => setWebSearchEnabled(event.target.checked)}
              />
              <span>Search the web</span>
              <small>
                {capabilities.web_search?.available
                  ? "Separate terms only; chat prompt is not sent"
                  : "Brave Search API key required"}
              </small>
            </label>
            {webSearchEnabled && (
              <input
                className="web-search-query"
                aria-label="Web search terms"
                value={webSearchQuery}
                maxLength={400}
                onChange={event => setWebSearchQuery(event.target.value)}
                placeholder="Search terms (common secret/code patterns are blocked)"
              />
            )}
            {modelError && <div className="model-error">{modelError}</div>}
            <textarea
              ref={inputRef}
              aria-label="Message AI Agent"
              placeholder="Message AI Agent..."
              value={input}
              maxLength={8000}
              rows={1}
              onChange={event => setInput(event.target.value)}
              onKeyDown={onComposerKeyDown}
              disabled={loading}
            />
            <div className="composer-bottom">
              <span className="composer-hint">AI can make mistakes. Check important information.</span>
              <div className="composer-actions">
                <span className={`char-count ${input.length > 7600 ? "near-limit" : ""}`}>
                  {input.length > 0 ? `${input.length}/8000` : ""}
                </span>
                <button
                  className="send-button"
                  type="submit"
                  disabled={!input.trim() || sending || loading}
                  aria-label="Send message"
                >
                  {sending ? "…" : "↑"}
                </button>
              </div>
            </div>
          </form>
        </footer>
      </main>

      {accountOpen && (
        <div
          className="modal-backdrop"
          onMouseDown={event => {
            if (event.target === event.currentTarget) setAccountOpen(false);
          }}
        >
          <section className="account-modal" aria-labelledby="account-title">
            <button className="modal-close" onClick={() => setAccountOpen(false)} aria-label="Close">×</button>
            <div className="welcome-symbol small">✦</div>
            <h2 id="account-title">{session === "guest" ? "Connect your account" : "Account"}</h2>
            <p>Sign in with the user or administrator token provided by your workspace operator to use your account chat history.</p>
            <form onSubmit={event => void signIn(event)}>
              <label htmlFor="access-token">Access token</label>
              <input
                id="access-token"
                type="password"
                autoComplete="current-password"
                placeholder="Paste your user/admin token"
                value={tokenDraft}
                onChange={event => setTokenDraft(event.target.value)}
              />
              <button className="modal-primary" type="submit">Sign in</button>
            </form>
            {session !== "guest" && (
              <button className="guest-button" onClick={() => void continueAsGuest()}>
                Switch to a guest session
              </button>
            )}
            <a className="modal-back-link" href="/">← Back to workflow console</a>
          </section>
        </div>
      )}
      {codingAgentOpen && (
        <div
          className="modal-backdrop"
          onMouseDown={event => {
            if (event.target === event.currentTarget) setCodingAgentOpen(false);
          }}
        >
          <section className="coding-agent-modal" aria-labelledby="coding-agent-title">
            <button
              className="modal-close"
              aria-label="Close coding agent"
              onClick={() => setCodingAgentOpen(false)}
            >
              ×
            </button>
            <div className="welcome-symbol small">{"</>"}</div>
            <h2 id="coding-agent-title">Project Coding Agent</h2>
            <p>
              Select source files and describe a change. The agent returns a
              patch proposal for review; it never edits files or runs commands.
            </p>
            <form onSubmit={event => void proposeCodingChange(event)}>
              <label htmlFor="coding-task">What should the agent change?</label>
              <textarea
                id="coding-task"
                maxLength={4000}
                rows={3}
                value={codingTask}
                onChange={event => setCodingTask(event.target.value)}
                placeholder="Describe the bug or feature and expected behavior."
              />
              <div className="coding-file-heading">
                <label htmlFor="coding-file-search">Workspace files</label>
                <span>{codingSelectedFiles.length}/8 selected</span>
              </div>
              <input
                id="coding-file-search"
                type="search"
                value={codingFileSearch}
                onChange={event => setCodingFileSearch(event.target.value)}
                placeholder="Filter files..."
              />
              {codingFilesLoading ? (
                <div className="coding-files-state">Loading workspace files...</div>
              ) : (
                <div className="coding-file-list">
                  {codingFiles
                    .filter(file =>
                      file.toLowerCase().includes(codingFileSearch.trim().toLowerCase()),
                    )
                    .map(file => (
                      <label className="coding-file-option" key={file}>
                        <input
                          type="checkbox"
                          checked={codingSelectedFiles.includes(file)}
                          disabled={
                            codingSubmitting ||
                            (
                              codingSelectedFiles.length >= 8 &&
                              !codingSelectedFiles.includes(file)
                            )
                          }
                          onChange={event => {
                            setCodingSelectedFiles(current =>
                              event.target.checked
                                ? [...current, file]
                                : current.filter(selected => selected !== file),
                            );
                          }}
                        />
                        <span>{file}</span>
                      </label>
                    ))}
                  {codingFiles.length === 0 && (
                    <div className="coding-files-state">No eligible source files found.</div>
                  )}
                </div>
              )}
              {codingFilesTruncated && (
                <small className="coding-agent-note">
                  Showing the first 500 eligible files. Use the filter to find files.
                </small>
              )}
              {codingFilesError && (
                <div className="coding-agent-error" role="alert">{codingFilesError}</div>
              )}
              {codingAgentError && (
                <div className="coding-agent-error" role="alert">{codingAgentError}</div>
              )}
              <button
                className="modal-primary"
                type="submit"
                disabled={
                  codingSubmitting ||
                  !codingTask.trim() ||
                  codingSelectedFiles.length === 0
                }
              >
                {codingSubmitting ? "Preparing proposal..." : "Generate patch proposal"}
              </button>
            </form>
            {codingProposal && (
              <div className="coding-proposal" aria-live="polite">
                <div className="coding-proposal-heading">
                  <strong>Review proposal</strong>
                  <span>{codingProposal.model}</span>
                </div>
                <pre>{codingProposal.proposal}</pre>
                <small>
                  Not applied. Review the diff and apply it through your normal
                  development workflow.
                </small>
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

function errorMessage(reason: unknown): string {
  if (reason instanceof ApiError) {
    return reason.status === 401
      ? "Your session is not authorized. Sign in again or continue as a guest."
      : reason.message;
  }
  return reason instanceof Error ? reason.message : "Something went wrong.";
}

function renderMessageContent(content: string) {
  const lines = content.split("\n");
  return lines.map((line, index) => {
    const source = line.match(/^\[(\d+)\]\s+(.+?)\s+—\s+(https?:\/\/\S+)$/);
    if (!source) {
      return <span key={index}>{line}{index < lines.length - 1 && <br />}</span>;
    }
    return (
      <span key={index}>
        [{source[1]}]{" "}
        <a href={source[3]} target="_blank" rel="noopener noreferrer">
          {source[2]}
        </a>
        {" — "}{source[3]}
        {index < lines.length - 1 && <br />}
      </span>
    );
  });
}
