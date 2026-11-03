import { useEffect, useRef, useState, type FormEvent } from "react";
import { Alert, AnimatedMarkdownAnswer, Button, MarkdownAnswer, StatusBadge, TextArea, TextInput } from "./components";
import { getCurrentUser, getIndexingStatus, getRepositories, createChatSession, getChatSessions, getChatSession, loginWithGoogle, logout, startIndexing, streamQuestion, type AuthUser, type ChatSession, type ChatSessionDetail, type Evidence, type IndexJob, type InvestigationStage, type QuestionResponse } from "./api";

type Theme = "light" | "dark";

type ConversationResponse = {
  answer: string;
  evidence: Evidence[];
  relevance_grade?: string;
  document_count?: number;
  retry_count?: number;
};

type ConversationTurn = {
  id: string;
  question: string;
  response: ConversationResponse | null;
  error: string;
  stages: Record<string, InvestigationStage>;
  isLoading: boolean;
  animateResponse: boolean;
};

function InvestigationTrail({ stages }: { stages: Record<string, InvestigationStage> }) {
  const steps = [
    ["question_received", "Question received"],
    ["context_retrieved", "Context retrieved"],
    ["evidence_graded", "Evidence graded"],
    ["answer_generated", "Answer generated"],
  ] as const;
  return (
    <ol className="source-trail compact-trail" aria-label="Investigation progress">
      {steps.map(([stage, label], index) => {
        const event = stages[stage];
        return <li className={event?.status === "completed" ? "trail-complete" : event?.status === "running" ? "trail-current" : ""} key={stage}><span className="trail-node">{event?.status === "completed" ? "OK" : index + 1}</span><span><strong>{label}</strong><small>{event?.message ?? "Waiting for this stage"}</small></span></li>;
      })}
    </ol>
  );
}

function App() {
  const [theme, setTheme] = useState<Theme>("light");
  const [query, setQuery] = useState("");
  const [repositories, setRepositories] = useState<string[]>([]);
  const [repositoryName, setRepositoryName] = useState("");
  const [error, setError] = useState("");
  const [isLoadingRepositories, setIsLoadingRepositories] = useState(true);
  const [indexUrl, setIndexUrl] = useState("");
  const [indexJob, setIndexJob] = useState<IndexJob | null>(null);
  const [indexError, setIndexError] = useState("");
  const [showIndexing, setShowIndexing] = useState(false);
  const [expandedEvidence, setExpandedEvidence] = useState<Record<string, boolean>>({});
  const [conversation, setConversation] = useState<ConversationTurn[]>([]);
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [authError, setAuthError] = useState("");
  const [profileImageFailed, setProfileImageFailed] = useState(false);
  const googleButton = useRef<HTMLDivElement>(null);
  const conversationRef = useRef<HTMLDivElement>(null);
  const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined;

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    setProfileImageFailed(false);
  }, [authUser?.picture_url]);

  useEffect(() => {
    getCurrentUser()
      .then(({ user }) => setAuthUser(user))
      .catch(() => setAuthUser(null))
      .finally(() => setAuthLoading(false));
  }, []);

  useEffect(() => {
    if (!authUser) return;
    getRepositories()
      .then(({ repositories: indexedRepositories }) => {
        const names = indexedRepositories.map(({ name }) => name);
        setRepositories(names);
        setRepositoryName(names[0] ?? "");
      })
      .catch((requestError: Error) => setError(requestError.message))
      .finally(() => setIsLoadingRepositories(false));
  }, [authUser]);
  useEffect(() => {
    if (!authUser || !repositoryName) {
      setChatSessions([]);
      return;
    }

    let cancelled = false;
    setIsLoadingSessions(true);

    getChatSessions(repositoryName)
      .then(({ sessions }) => {
        if (!cancelled) {
          setChatSessions(sessions);
        }
      })
      .catch((requestError: Error) => {
        if (!cancelled) setError(requestError.message);
      })
      .finally(() => {
        if (!cancelled) setIsLoadingSessions(false);
      });

    return () => {
      cancelled = true;
    };
  }, [authUser, repositoryName]);
  useEffect(() => {
    if (authUser || !googleClientId || !googleButton.current) return;
    let cancelled = false;
    let attempts = 0;
    let timer: number | undefined;
    const renderGoogleButton = () => {
      if (cancelled || !googleButton.current) return;
      if (!window.google) {
        attempts += 1;
        if (attempts < 50) timer = window.setTimeout(renderGoogleButton, 100);
        else setAuthError("Google sign-in could not load. Check your network connection and reload.");
        return;
      }
      window.google.accounts.id.initialize({
        client_id: googleClientId,
        callback: ({ credential }) => {
          setAuthError("");
          loginWithGoogle(credential)
            .then(({ user }) => setAuthUser(user))
            .catch((requestError: Error) => setAuthError(requestError.message));
        },
      });
      googleButton.current.replaceChildren();
      window.google.accounts.id.renderButton(googleButton.current, {
        theme: "outline",
        size: "large",
        width: 280,
        text: "signin_with",
        shape: "rectangular",
      });
    };
    renderGoogleButton();
    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [authLoading, authUser, googleClientId]);

  useEffect(() => {
    if (!indexJob || !["queued", "running"].includes(indexJob.status)) return;
    const timer = window.setInterval(() => {
      getIndexingStatus(indexJob.job_id).then((job) => {
        setIndexJob(job);
        if (job.status === "completed") {
          getRepositories().then(({ repositories: next }) => {
            const names = next.map(({ name }) => name);
            setRepositories(names);
            if (job.repository_name) setRepositoryName(job.repository_name);
          });
        }
      }).catch((requestError: Error) => setIndexError(requestError.message));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [indexJob?.job_id, indexJob?.status]);

  function submitIndexing(event: FormEvent) {
    event.preventDefault();
    if (!indexUrl.trim() || indexJob?.status === "running" || indexJob?.status === "queued") return;
    setIndexError("");
    setIndexJob(null);
    startIndexing(indexUrl.trim())
      .then(setIndexJob)
      .catch((requestError: Error) => setIndexError(requestError.message));
  }
  async function openChatSession(session: ChatSession) {
  try {
    setError("");

    const detail = await getChatSession(session.id);

    const restoredConversation: ConversationTurn[] = [];
    let pendingTurn: ConversationTurn | null = null;

    for (const message of detail.messages) {
      if (message.role === "user") {
        pendingTurn = {
          id: message.id,
          question: message.content,
          response: null,
          error: "",
          stages: {},
          isLoading: false,
          animateResponse: false,
        };

        restoredConversation.push(pendingTurn);
      } else if (message.role === "assistant" && pendingTurn) {
        pendingTurn.response = {
          answer: message.content,
          evidence: message.evidence,
        };
        pendingTurn.isLoading = false;
        pendingTurn.animateResponse = false;

        pendingTurn = null;
      }
    }

    setConversation(restoredConversation);
    setActiveSessionId(session.id);
    setExpandedEvidence({});
  } catch (requestError) {
    setError((requestError as Error).message);
  }
}
  async function submitQuery() {
  const question = query.trim();

  if (!question || !repositoryName || conversation.some((turn) => turn.isLoading)) {
    return;
  }

  const turnId = `${Date.now()}-${conversation.length}`;

  const turn: ConversationTurn = {
    id: turnId,
    question,
    response: null,
    error: "",
    stages: {},
    isLoading: true,
    animateResponse: true,
  };

  setConversation((current) => [...current, turn]);
  setQuery("");
  setError("");

  window.requestAnimationFrame(() => {
    conversationRef.current?.scrollTo({
      top: conversationRef.current.scrollHeight,
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "auto"
        : "smooth",
    });
  });

  try {
    let sessionId = activeSessionId;

    // Create a persistent session for the first question.
    if (!sessionId) {
      const session = await createChatSession(
        repositoryName,
        question.slice(0, 80),
      );

      sessionId = session.id;
      setActiveSessionId(session.id);
      setChatSessions((current) => [session, ...current]);
    }

    const response = await streamQuestion(
      repositoryName,
      question,
      sessionId,
      (stage: InvestigationStage) => {
        setConversation((current) =>
          current.map((item) =>
            item.id === turnId
              ? {
                  ...item,
                  stages: {
                    ...item.stages,
                    [stage.stage]: stage,
                  },
                }
              : item,
          ),
        );
      },
    );

    setConversation((current) =>
      current.map((item) =>
        item.id === turnId
          ? { ...item, response, isLoading: false }
          : item,
      ),
    );
  } catch (requestError) {
    setConversation((current) =>
      current.map((item) =>
        item.id === turnId
          ? {
              ...item,
              error: (requestError as Error).message,
              isLoading: false,
            }
          : item,
      ),
    );
  }
}

  if (authLoading) {
    return <div className="auth-gate"><div className="loading-state" role="status"><span className="loading-bar" /><strong>Preparing your workspace…</strong></div></div>;
  }

  if (!authUser) {
    return (
      <div className="auth-gate">
        <div className="auth-card">
          <a className="wordmark" href="/" aria-label="RepoPilot home"><span className="mark" aria-hidden="true"><span /><span /><span /></span><span>RepoPilot</span></a>
          <span className="eyebrow">Evidence Field</span>
          <h1>Sign in to your repository workspace.</h1>
          <p>Use your Google account to access private repository context and source evidence.</p>
          <div ref={googleButton} className="google-button" aria-label="Sign in with Google" />
          {!googleClientId && <Alert tone="danger" title="Google sign-in is not configured">Set VITE_GOOGLE_CLIENT_ID in frontend/.env.</Alert>}
          {authError && <Alert tone="danger" title="Sign-in failed">{authError}</Alert>}
          <div className="auth-theme-row"><span>Theme</span><Button variant="ghost" onClick={() => setTheme(theme === "light" ? "dark" : "light")}>{theme === "light" ? "Dark" : "Light"} mode</Button></div>
        </div>
      </div>
    );
  }

  function signOut() {
    logout().then(() => {
      setAuthUser(null);
      setRepositories([]);
      setConversation([]);
    }).catch((requestError: Error) => setAuthError(requestError.message));
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="wordmark" href="/" aria-label="RepoPilot home">
          <span className="mark" aria-hidden="true">
            <span />
            <span />
            <span />
          </span>
          <span>RepoPilot</span>
        </a>
        <div className="topbar-context">
          <span className="context-label">Workspace</span>
          <label className="sr-only" htmlFor="workspace-repository">Active repository</label>
          <select
            id="workspace-repository"
            className="repository-selector"
            value={repositoryName}
            onChange={(event) => {
              setActiveSessionId(null);
              setRepositoryName(event.target.value);
              setConversation([]);
            }}
            disabled={isLoadingRepositories || repositories.length === 0}
          >
            {!repositoryName && <option value="">No indexed repository</option>}
            {repositories.map((name) => <option value={name} key={name}>{name}</option>)}
          </select>
        </div>
        <div className="topbar-actions">
          <Button variant="ghost" aria-label="Open keyboard shortcuts">Shortcuts <kbd>Ctrl K</kbd></Button>
          <Button
            variant="ghost"
            aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}
            onClick={() => setTheme(theme === "light" ? "dark" : "light")}
          >
            <span className="theme-indicator" aria-hidden="true" />
            {theme === "light" ? "Dark" : "Light"}
          </Button>
          <details className="profile-menu">
            <summary aria-label="Open profile menu">
              {authUser.picture_url && !profileImageFailed ? <img src={authUser.picture_url} alt="" onError={() => setProfileImageFailed(true)} /> : <span>{(authUser.name ?? authUser.email).slice(0, 1).toUpperCase()}</span>}
            </summary>
            <div className="profile-popover">
              <strong>{authUser.name ?? "Google account"}</strong>
              <small>{authUser.email}</small>
              <Button variant="ghost" onClick={signOut}>Sign out</Button>
            </div>
          </details>
        </div>
      </header>

      <div className="workspace">
        <aside className="rail" aria-label="Repository navigation">
          <div className="rail-section">
            <div className="rail-heading">
              <span>Repositories</span>
              <span className="mono">{repositories.length}</span>
            </div>
            {repositories.map((name) => (
              <button
                className={`repo-item ${name === repositoryName ? "repo-item-active" : ""}`}
                key={name}
                onClick={() => {
                  setActiveSessionId(null);
                  setRepositoryName(name);
                  setConversation([]);
                }}
              >
                <span className="repo-glyph">{name.slice(0, 1).toUpperCase()}</span>
                <span><strong>{name}</strong><small>Indexed repository</small></span>
                {name === repositoryName && <span className="active-dot" aria-label="Currently selected" />}
              </button>
            ))}
            {!isLoadingRepositories && repositories.length === 0 && (
              <p className="field-hint">No indexed repositories yet.</p>
            )}
          </div>
          <div className="rail-section">
            <div className="rail-heading">
              <span>Conversations</span>
              <span className="mono">{chatSessions.length}</span>
            </div>

            <button
              className="repo-item"
              onClick={() => {
                setActiveSessionId(null);
                setConversation([]);
                setExpandedEvidence({});
                setError("");
              }}
            >
              <span className="repo-glyph">+</span>
              <span>
                <strong>New conversation</strong>
                <small>Start a fresh discussion</small>
              </span>
            </button>

            {isLoadingSessions && (
              <p className="field-hint">Loading conversations…</p>
            )}

            {!isLoadingSessions && chatSessions.map((session) => (
              <button
                className={`repo-item ${session.id === activeSessionId ? "repo-item-active" : ""}`}
                key={session.id}
                onClick={() => openChatSession(session)}
              >
                <span className="repo-glyph">C</span>
                <span>
                  <strong>{session.title || "Untitled conversation"}</strong>
                  <small>{new Date(session.updated_at).toLocaleDateString()}</small>
                </span>
                {session.id === activeSessionId && (
                  <span className="active-dot" aria-label="Currently selected" />
                )}
              </button>
            ))}

            {!isLoadingSessions && chatSessions.length === 0 && (
              <p className="field-hint">No conversations yet.</p>
            )}
          </div>
          <div className="rail-footer">
            <small className="field-hint">Repository context is stored locally.</small>
          </div>
        </aside>

        <main className="main-content">
          <div className="page-heading">
            <div>
              <h1>Repository conversation.</h1>
              <p className="lede">Ask follow-up questions and keep the evidence trail in context.</p>
            </div>
            <Button variant="secondary" onClick={() => setShowIndexing(true)}>Index repository</Button>
          </div>

          <div className="conversation-thread" ref={conversationRef} aria-live="polite">
            {conversation.length === 0 ? (
              <div className="conversation-empty">
                <span className="empty-mark" aria-hidden="true">•••</span>
                <h2>Ask about your repository.</h2>
                <p>Questions, follow-ups, and the source evidence behind each answer will stay together here.</p>
              </div>
            ) : conversation.map((turn) => {
              const evidence = turn.response?.evidence ?? [];
              return (
                <article className="conversation-turn" key={turn.id}>
                  <div className="user-message">
                    <span className="message-label">You</span>
                    <p>{turn.question}</p>
                  </div>
                  <div className="assistant-message">
                    <div className="assistant-heading">
                      <span className="assistant-mark" aria-hidden="true">R</span>
                      <span>RepoPilot</span>
                      {turn.response?.relevance_grade && (
                          <StatusBadge
                            tone={turn.response.relevance_grade === "RELEVANT" ? "evidence" : "warning"}
                          >
                            {turn.response.relevance_grade === "RELEVANT" ? "Grounded" : "Needs review"}
                          </StatusBadge>
                        )}
                    </div>
                    {turn.isLoading ? (
                      <div className="loading-state conversation-loading" role="status">
                        <span className="loading-bar" />
                        <strong>Following the evidence trail…</strong>
                        <p>{turn.stages.answer_generated?.message ?? "Retrieving and grading repository context."}</p>
                        <InvestigationTrail stages={turn.stages} />
                      </div>
                    ) : turn.error ? (
                      <Alert tone="danger" title="Investigation failed">{turn.error}</Alert>
                    ) : turn.response ? (
                      <>
                        <div className="answer">
                          {turn.animateResponse
                            ? <AnimatedMarkdownAnswer markdown={turn.response.answer} />
                            : <MarkdownAnswer markdown={turn.response.answer} />}
                          {turn.response.document_count !== undefined && (
                            <p>
                              {turn.response.document_count} source chunks were retrieved and graded{" "}
                              {turn.response.relevance_grade?.toLowerCase() ?? "unknown"}.
                            </p>
                          )}
                        </div>
                        {evidence.length > 0 && (
                          <details className="sources-disclosure">
                            <summary>Sources <span>{evidence.length}</span></summary>
                            <div className="evidence-scroller" tabIndex={0} aria-label="Horizontally scrollable source evidence">
                              {evidence.map((item: Evidence) => {
                                const evidenceKey = `${turn.id}:${item.file_path}:${item.start_line}`;
                                return (
                                  <article className="evidence-card" key={evidenceKey}>
                                    <div className="evidence-meta"><StatusBadge tone="evidence">Retrieved</StatusBadge><span className="mono">lines {item.start_line ?? "?"}–{item.end_line ?? "?"}</span></div>
                                    <strong className="evidence-path">{item.file_path}</strong>
                                    <span className="evidence-symbol">{item.symbol || "Module scope"}</span>
                                    <div className="evidence-details"><span className="mono">score {item.reranker_score?.toFixed(3) ?? "n/a"}</span><button className="evidence-toggle" onClick={() => setExpandedEvidence((current) => ({ ...current, [evidenceKey]: !current[evidenceKey] }))} aria-expanded={Boolean(expandedEvidence[evidenceKey])}>{expandedEvidence[evidenceKey] ? "Collapse" : "Expand"}</button></div>
                                    <pre className={`code-block ${expandedEvidence[evidenceKey] ? "code-block-expanded" : ""}`} aria-label={`Source from ${item.file_path}`}><code>{expandedEvidence[evidenceKey] ? item.content : item.content.slice(0, 420)}{!expandedEvidence[evidenceKey] && item.content.length > 420 ? "…" : ""}</code></pre>
                                  </article>
                                );
                              })}
                            </div>
                          </details>
                        )}
                      </>
                    ) : null}
                  </div>
                </article>
              );
            })}
          </div>

          <form className="conversation-composer" onSubmit={(event) => { event.preventDefault(); submitQuery(); }}>
            <div className="composer-input-row">
              <TextArea label="Message RepoPilot" aria-label="Message RepoPilot" placeholder="Ask a follow-up about the repository…" value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} rows={2} />
              <Button variant="primary" type="submit" disabled={conversation.some((turn) => turn.isLoading) || !query.trim() || !repositoryName}>Send <span aria-hidden="true">↗</span></Button>
            </div>
            <span className="composer-hint">Enter to send · Shift+Enter for a new line</span>
          </form>
        </main>
      </div>
      {showIndexing && (
        <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setShowIndexing(false); }}>
          <section className="dialog" role="dialog" aria-modal="true" aria-labelledby="index-dialog-title">
            <div className="panel-heading"><h2 id="index-dialog-title">Index a repository</h2></div>
            <form className="dialog-body" onSubmit={submitIndexing}>
              <TextInput label="GitHub repository URL" value={indexUrl} onChange={(event) => setIndexUrl(event.target.value)} placeholder="https://github.com/owner/repository" disabled={indexJob?.status === "queued" || indexJob?.status === "running"} />
              <p className="field-hint">Indexing runs in the background. Existing local clones are reused.</p>
              {indexError && <Alert tone="danger" title="Indexing could not start">{indexError}</Alert>}
              {indexJob && <div className={`index-job index-job-${indexJob.status}`}><strong>{indexJob.message}</strong><span>Current stage: {indexJob.stage}</span><div className="progress-track" role="progressbar" aria-label="Repository indexing progress" aria-valuetext={indexJob.status === "running" ? `${indexJob.stage} in progress` : indexJob.status}><span className={indexJob.status === "running" ? "progress-indeterminate" : indexJob.status === "completed" ? "progress-complete" : "progress-queued"} /></div><div className="completed-stages"><span>Completed stages</span><strong>{indexJob.completed_stages.length ? indexJob.completed_stages.join(" · ") : "None yet"}</strong></div>{indexJob.error && <p>{indexJob.error}</p>}{indexJob.chunk_count && <span>{indexJob.chunk_count} chunks stored</span>}</div>}
              <div className="dialog-actions">
                {indexJob?.status !== "completed" && <Button variant="secondary" type="button" onClick={() => setShowIndexing(false)}>Cancel</Button>}
                <Button variant={indexJob?.status === "completed" ? "secondary" : "primary"} type={indexJob?.status === "completed" ? "button" : "submit"} onClick={indexJob?.status === "completed" ? () => setShowIndexing(false) : undefined} disabled={indexJob?.status === "queued" || indexJob?.status === "running"}>
                  {indexJob?.status === "queued" || indexJob?.status === "running" ? "Indexing…" : indexJob?.status === "completed" ? "Done" : "Start indexing"}
                </Button>
              </div>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}

export default App;
