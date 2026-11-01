import { useEffect, useState, type FormEvent } from "react";
import { Alert, Button, MarkdownAnswer, Panel, StatusBadge, TextArea, TextInput } from "./components";
import { getIndexingStatus, getRepositories, startIndexing, streamQuestion, type Evidence, type IndexJob, type InvestigationStage, type QuestionResponse } from "./api";

type Theme = "light" | "dark";

function App() {
  const [theme, setTheme] = useState<Theme>("light");
  const [query, setQuery] = useState("");
  const [repositories, setRepositories] = useState<string[]>([]);
  const [repositoryName, setRepositoryName] = useState("");
  const [result, setResult] = useState<QuestionResponse | null>(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingRepositories, setIsLoadingRepositories] = useState(true);
  const [indexUrl, setIndexUrl] = useState("");
  const [indexJob, setIndexJob] = useState<IndexJob | null>(null);
  const [indexError, setIndexError] = useState("");
  const [showIndexing, setShowIndexing] = useState(false);
  const [expandedEvidence, setExpandedEvidence] = useState<Record<string, boolean>>({});
  const [investigationStages, setInvestigationStages] = useState<Record<string, InvestigationStage>>({});

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    getRepositories()
      .then(({ repositories: indexedRepositories }) => {
        const names = indexedRepositories.map(({ name }) => name);
        setRepositories(names);
        setRepositoryName(names[0] ?? "");
      })
      .catch((requestError: Error) => setError(requestError.message))
      .finally(() => setIsLoadingRepositories(false));
  }, []);

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

  function submitQuery() {
    if (!query.trim() || !repositoryName) return;
    setIsLoading(true);
    setError("");
    setResult(null);
    setInvestigationStages({});
    streamQuestion(repositoryName, query.trim(), (stage) => {
      setInvestigationStages((current) => ({ ...current, [stage.stage]: stage }));
    })
      .then(setResult)
      .catch((requestError: Error) => setError(requestError.message))
      .finally(() => setIsLoading(false));
  }

  const evidence = result?.evidence ?? [];
  const selectedRepository = repositoryName || "No indexed repository";

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
          <strong>{selectedRepository}</strong>
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
                  setRepositoryName(name);
                  setResult(null);
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
          <div className="rail-footer">
            <small className="field-hint">Repository context is stored locally.</small>
          </div>
        </aside>

        <main className="main-content">
          <div className="page-heading">
            <div>
              <h1>Ask the repository.</h1>
              <p className="lede">Trace a question from intent to source evidence, without losing the thread.</p>
            </div>
            <Button variant="secondary" onClick={() => setShowIndexing(true)}>Index repository</Button>
          </div>

          <section className="composer-section" aria-labelledby="question-title">
            <div className="section-title">
              <span className="accent-line" aria-hidden="true" />
              <h2 id="question-title">Start an investigation</h2>
            </div>
            <div className="composer">
              <TextInput
                label="Repository"
                value={repositoryName}
                onChange={(event) => setRepositoryName(event.target.value)}
                list="repository-options"
                placeholder="Select an indexed repository"
                disabled={isLoadingRepositories}
              />
              <datalist id="repository-options">
                {repositories.map((name) => <option value={name} key={name} />)}
              </datalist>
              <TextArea
                label="Your question"
                aria-label="Your question"
                placeholder="e.g. Where is repository context assembled before generation?"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                rows={3}
              />
              <div className="composer-footer">
                <span className="composer-hint">Searches symbols, files, docs, and indexed context.</span>
                <Button variant="primary" onClick={submitQuery} disabled={isLoading || !query.trim() || !repositoryName}>
                  {isLoading ? "Retrieving…" : "Find evidence"} <span aria-hidden="true">↗</span>
                </Button>
              </div>
            </div>
          </section>

          <div className="content-grid">
            <div className="primary-column">
              {error ? (
                <Panel title="Answer">
                  <Alert tone="danger" title="Investigation failed">{error}</Alert>
                </Panel>
              ) : isLoading ? (
                <Panel title="Answer">
                  <div className="loading-state" role="status"><span className="loading-bar" /><strong>Following the evidence trail…</strong><p>{investigationStages.answer_generated?.message ?? "Retrieving and grading repository context."}</p></div>
                </Panel>
              ) : result ? (
                <Panel title="Answer" action={<StatusBadge tone={result.relevance_grade === "RELEVANT" ? "evidence" : "warning"}>{result.relevance_grade === "RELEVANT" ? "Grounded" : "Needs review"}</StatusBadge>}>
                  <div className="answer">
                    <MarkdownAnswer markdown={result.answer} />
                    <p>{result.document_count} source chunks were retrieved and graded {result.relevance_grade.toLowerCase()}.</p>
                    <div className="answer-actions">
                      <Button variant="secondary" onClick={() => setResult(null)}>New investigation</Button>
                    </div>
                  </div>
                </Panel>
              ) : (
                <Panel title="Answer">
                  <div className="empty-state">
                    <span className="empty-mark" aria-hidden="true">•••</span>
                    <h3>Your evidence trail will appear here.</h3>
                    <p>Ask a question to see a concise answer alongside the files and symbols that support it.</p>
                  </div>
                </Panel>
              )}

            </div>

            <aside className="evidence-column" aria-label="Source evidence">
              <Panel title="Source evidence">
                {evidence.length > 0 ? evidence.map((item: Evidence) => (
                  <div className="evidence-card" key={`${item.file_path}:${item.start_line}`}>
                    <div className="evidence-meta">
                      <StatusBadge tone="evidence">Retrieved evidence</StatusBadge>
                      <span className="mono">lines {item.start_line ?? "?"}–{item.end_line ?? "?"}</span>
                    </div>
                    <strong className="evidence-path">{item.file_path}</strong>
                    <span className="evidence-symbol">{item.symbol || "Module scope"}</span>
                    <div className="evidence-details">
                      <span className="mono">reranker score {item.reranker_score?.toFixed(3) ?? "n/a"}</span>
                      <button className="evidence-toggle" onClick={() => setExpandedEvidence((current) => ({ ...current, [`${item.file_path}:${item.start_line}`]: !current[`${item.file_path}:${item.start_line}`] }))} aria-expanded={Boolean(expandedEvidence[`${item.file_path}:${item.start_line}`])}>
                        {expandedEvidence[`${item.file_path}:${item.start_line}`] ? "Collapse preview" : "Expand preview"}
                      </button>
                    </div>
                    <pre className={`code-block ${expandedEvidence[`${item.file_path}:${item.start_line}`] ? "code-block-expanded" : ""}`} aria-label={`Source from ${item.file_path}`}><code>{expandedEvidence[`${item.file_path}:${item.start_line}`] ? item.content : item.content.slice(0, 420)}{!expandedEvidence[`${item.file_path}:${item.start_line}`] && item.content.length > 420 ? "…" : ""}</code></pre>
                  </div>
                )) : (
                  <div className="empty-state">
                    <h3>No evidence yet.</h3>
                    <p>Submit a question to see the actual retrieved source chunks.</p>
                  </div>
                )}
              </Panel>

              <Panel title="Evidence trail" className="trail-panel">
                <ol className="source-trail">
                  {[
                    ["question_received", "Question received"],
                    ["context_retrieved", "Context retrieved"],
                    ["evidence_graded", "Evidence graded"],
                    ["answer_generated", "Answer generated"],
                  ].map(([stage, label], index) => {
                    const event = investigationStages[stage];
                    return <li className={event?.status === "completed" ? "trail-complete" : event?.status === "running" ? "trail-current" : ""} key={stage}><span className="trail-node">{event?.status === "completed" ? "OK" : index + 1}</span><span><strong>{label}</strong><small>{event?.message ?? "Waiting for this stage"}</small></span></li>;
                  })}
                </ol>
              </Panel>
            </aside>
          </div>
        </main>
      </div>
      {showIndexing && (
        <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setShowIndexing(false); }}>
          <section className="dialog" role="dialog" aria-modal="true" aria-labelledby="index-dialog-title">
            <div className="panel-heading"><h2 id="index-dialog-title">Index a repository</h2><Button variant="ghost" onClick={() => setShowIndexing(false)}>Close</Button></div>
            <form className="dialog-body" onSubmit={submitIndexing}>
              <TextInput label="GitHub repository URL" value={indexUrl} onChange={(event) => setIndexUrl(event.target.value)} placeholder="https://github.com/owner/repository" disabled={indexJob?.status === "queued" || indexJob?.status === "running"} />
              <p className="field-hint">Indexing runs in the background. Existing local clones are reused.</p>
              {indexError && <Alert tone="danger" title="Indexing could not start">{indexError}</Alert>}
              {indexJob && <div className={`index-job index-job-${indexJob.status}`}><strong>{indexJob.message}</strong><span>Current stage: {indexJob.stage}</span><div className="progress-track" role="progressbar" aria-label="Repository indexing progress" aria-valuetext={indexJob.status === "running" ? `${indexJob.stage} in progress` : indexJob.status}><span className={indexJob.status === "running" ? "progress-indeterminate" : indexJob.status === "completed" ? "progress-complete" : "progress-queued"} /></div><div className="completed-stages"><span>Completed stages</span><strong>{indexJob.completed_stages.length ? indexJob.completed_stages.join(" · ") : "None yet"}</strong></div>{indexJob.error && <p>{indexJob.error}</p>}{indexJob.chunk_count && <span>{indexJob.chunk_count} chunks stored</span>}</div>}
              <div className="dialog-actions"><Button variant="secondary" type="button" onClick={() => setShowIndexing(false)}>Cancel</Button><Button variant="primary" type="submit" disabled={!indexUrl.trim() || indexJob?.status === "queued" || indexJob?.status === "running"}>{indexJob?.status === "queued" || indexJob?.status === "running" ? "Indexing…" : "Start indexing"}</Button></div>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}

export default App;
