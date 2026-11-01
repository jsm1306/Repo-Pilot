export type RepositorySummary = {
  name: string;
};

export type Evidence = {
  file_path: string;
  symbol: string;
  symbol_type: string;
  language: string;
  start_line: number | null;
  end_line: number | null;
  content: string;
  reranker_score: number | null;
};

export type QuestionResponse = {
  repository_name: string;
  question: string;
  answer: string;
  document_count: number;
  relevance_grade: string;
  retry_count: number;
  evidence: Evidence[];
};

export type IndexJob = {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  stage: string;
  message: string;
  repository_name: string | null;
  chunk_count: number | null;
  error: string | null;
  completed_stages: string[];
  updated_at: string;
};

export type InvestigationStage = {
  type: "stage";
  stage: string;
  status: "running" | "completed";
  message: string;
  document_count?: number;
  relevance_grade?: string;
};

type ErrorPayload = {
  detail?: {
    message?: string;
  };
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as ErrorPayload | null;
    throw new Error(payload?.detail?.message ?? "The RepoPilot API could not complete the request.");
  }
  return response.json() as Promise<T>;
}

export function getRepositories(): Promise<{ repositories: RepositorySummary[] }> {
  return request("/api/repositories");
}

export function askQuestion(repository_name: string, question: string): Promise<QuestionResponse> {
  return request("/api/questions", {
    method: "POST",
    body: JSON.stringify({ repository_name, question }),
  });
}

export function startIndexing(repo_url: string): Promise<IndexJob> {
  return request("/api/indexing", {
    method: "POST",
    body: JSON.stringify({ repo_url }),
  });
}

export function getIndexingStatus(jobId: string): Promise<IndexJob> {
  return request(`/api/indexing/${jobId}`);
}

export function streamQuestion(
  repositoryName: string,
  question: string,
  onStage: (event: InvestigationStage) => void,
): Promise<QuestionResponse> {
  const params = new URLSearchParams({ repository_name: repositoryName, question });
  return new Promise((resolve, reject) => {
    const source = new EventSource(`/api/questions/stream?${params.toString()}`);
    source.onmessage = (event) => {
      const payload = JSON.parse(event.data) as InvestigationStage | { type: "complete"; response: QuestionResponse } | { type: "error"; message: string };
      if (payload.type === "stage") {
        onStage(payload);
      } else if (payload.type === "complete") {
        source.close();
        resolve(payload.response);
      } else {
        source.close();
        reject(new Error(payload.message));
      }
    };
    source.onerror = () => {
      source.close();
      reject(new Error("The live investigation connection was interrupted."));
    };
  });
}
