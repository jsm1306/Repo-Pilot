export type RepositorySummary = {
  name: string;
};

export type AuthUser = {
  id: string;
  email: string;
  name: string | null;
  picture_url: string | null;
  is_active: boolean;
};

export type AuthResponse = {
  user: AuthUser;
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

export type ChatSession = {
  id: string;
  repository_name: string;
  title: string | null;
  created_at: string;
  updated_at: string;
};

export type ChatSessionListResponse = {
  sessions: ChatSession[];
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  evidence: Evidence[];
};

export type ChatSessionDetail = ChatSession & {
  messages: ChatMessage[];
};

export type CreateChatSessionRequest = {
  repository_name: string;
  title?: string | null;
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

export type GoogleCredentialResponse = {
  credential: string;
};

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (options: {
            client_id: string;
            callback: (response: GoogleCredentialResponse) => void;
          }) => void;
          renderButton: (element: HTMLElement, options: Record<string, string | number>) => void;
        };
      };
    };
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const csrfToken = document.cookie
    .split("; ")
    .find((cookie) => cookie.startsWith("repopilot_csrf="))
    ?.split("=")[1];
  const headers = new Headers(init?.headers);
  headers.set("Content-Type", "application/json");
  if (csrfToken && init?.method && init.method !== "GET") {
    headers.set("X-CSRF-Token", decodeURIComponent(csrfToken));
  }
  const response = await fetch(path, {
    ...init,
    credentials: "same-origin",
    headers,
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as ErrorPayload | null;
    throw new Error(
      payload?.detail?.message ??
        "The RepoPilot API could not complete the request.",
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export function getCurrentUser(): Promise<AuthResponse> {
  return request("/api/auth/me");
}

export function loginWithGoogle(credential: string): Promise<AuthResponse> {
  return request("/api/auth/google", {
    method: "POST",
    body: JSON.stringify({ credential }),
  });
}

export function logout(): Promise<void> {
  return request("/api/auth/logout", { method: "POST" }).then(() => undefined);
}

export function getRepositories(): Promise<{ repositories: RepositorySummary[] }> {
  return request("/api/repositories");
}

export function createChatSession(
  repository_name: string,
  title?: string,
): Promise<ChatSession> {
  return request("/api/chat/sessions", {
    method: "POST",
    body: JSON.stringify({ repository_name, title }),
  });
}

export function getChatSessions(
  repositoryName?: string,
): Promise<ChatSessionListResponse> {
  const params = new URLSearchParams();

  if (repositoryName) {
    params.set("repository_name", repositoryName);
  }

  const query = params.toString();
  return request(`/api/chat/sessions${query ? `?${query}` : ""}`);
}

export function getChatSession(
  sessionId: string,
): Promise<ChatSessionDetail> {
  return request(`/api/chat/sessions/${sessionId}`);
}

export function renameChatSession(
  sessionId: string,
  title: string,
): Promise<ChatSession> {
  return request(`/api/chat/sessions/${sessionId}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
}

export function deleteChatSession(sessionId: string): Promise<void> {
  return request(`/api/chat/sessions/${sessionId}`, {
    method: "DELETE",
  });
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
  sessionId: string,
  onStage: (event: InvestigationStage) => void,
): Promise<QuestionResponse> {
  const params = new URLSearchParams({repository_name: repositoryName, question, session_id: sessionId,});
  return new Promise((resolve, reject) => {
    const source = new EventSource(`/api/questions/stream?${params.toString()}`);
    source.onmessage = (event) => {
      const payload = JSON.parse(event.data) as
        | InvestigationStage
        | { type: "complete"; response: QuestionResponse }
        | { type: "error"; code: string; message: string };

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
