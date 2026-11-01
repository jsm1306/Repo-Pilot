import re
import threading
import uuid
import json
import queue
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.embedder import Embedder
from app.langchain_llm import RepoPilotLLM
from app.langchain_retriever import RepoPilotRetriever
from app.graph import RepoPilotGraph
from app.reranker import Reranker
from app.vector_store import VectorStore
from app.indexing_service import index_repository


class HealthResponse(BaseModel):
    status: str


class RepositorySummary(BaseModel):
    name: str


class RepositoriesResponse(BaseModel):
    repositories: list[RepositorySummary]


class QuestionRequest(BaseModel):
    repository_name: str = Field(min_length=1, max_length=255)
    question: str = Field(min_length=1, max_length=4000)


class EvidenceResponse(BaseModel):
    file_path: str
    symbol: str
    symbol_type: str
    language: str
    start_line: int | None = None
    end_line: int | None = None
    content: str
    reranker_score: float | None = None


class QuestionResponse(BaseModel):
    repository_name: str
    question: str
    answer: str
    document_count: int
    relevance_grade: str
    retry_count: int
    evidence: list[EvidenceResponse]


class ErrorResponse(BaseModel):
    code: str
    message: str


class IndexRequest(BaseModel):
    repo_url: str = Field(min_length=1, max_length=2048)


class IndexJobResponse(BaseModel):
    job_id: str
    status: str
    stage: str
    message: str
    repository_name: str | None = None
    chunk_count: int | None = None
    error: str | None = None
    completed_stages: list[str] = Field(default_factory=list)
    updated_at: datetime


jobs: dict[str, IndexJobResponse] = {}
jobs_lock = threading.Lock()
INDEX_STAGES = ["cloning", "analyzing", "reading", "chunking", "embedding", "storing"]


app = FastAPI(title="RepoPilot API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/api/repositories", response_model=RepositoriesResponse)
def repositories() -> RepositoriesResponse:
    try:
        names = VectorStore().get_repositories()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "vector_store_unavailable", "message": "The repository index is unavailable."},
        ) from exc

    return RepositoriesResponse(
        repositories=[RepositorySummary(name=name) for name in names]
    )


def _build_question_graph(repository_name: str) -> RepoPilotGraph:
    vector_store = VectorStore()
    repositories = vector_store.get_repositories()
    if repository_name not in repositories:
        raise ValueError("repository_not_indexed")

    retriever = RepoPilotRetriever(
        embedder=Embedder(),
        vector_store=vector_store,
        reranker=Reranker(),
        repository_name=repository_name,
    )
    return RepoPilotGraph(retriever=retriever, llm=RepoPilotLLM())


def _run_question(
    request: QuestionRequest,
    event_callback: Any = None,
) -> dict[str, Any]:
    return _build_question_graph(request.repository_name).run_with_state(
        request.question,
        event_callback=event_callback,
    )


def _validate_repository_url(repo_url: str) -> str:
    parsed = urlparse(repo_url)
    if parsed.scheme != "https" or parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        raise ValueError("Enter an HTTPS GitHub repository URL.")
    if not re.fullmatch(r"/[^/]+/[^/]+/?", parsed.path):
        raise ValueError("Use a repository URL in the form https://github.com/owner/repository.")
    return parsed.path.rstrip("/").split("/")[-1].removesuffix(".git")


def _update_job(job_id: str, **changes: Any) -> None:
    with jobs_lock:
        current = jobs[job_id]
        stage = changes.get("stage")
        completed_stages = list(current.completed_stages)
        if stage in INDEX_STAGES:
            completed_stages = INDEX_STAGES[:INDEX_STAGES.index(stage)]
        jobs[job_id] = jobs[job_id].model_copy(update={
            **changes,
            "completed_stages": changes.get("completed_stages", completed_stages),
            "updated_at": datetime.now(timezone.utc),
        })


def _index_in_background(job_id: str, repo_url: str) -> None:
    try:
        def progress(stage: str, message: str) -> None:
            _update_job(job_id, status="running", stage=stage, message=message)

        result = index_repository(repo_url, progress=progress)
        _update_job(
            job_id,
            status="completed",
            stage="complete",
            message="Repository indexing completed.",
            repository_name=result["repository_name"],
            chunk_count=result["chunk_count"],
            completed_stages=["cloning", "analyzing", "reading", "chunking", "embedding", "storing"],
        )
    except Exception:
        _update_job(
            job_id,
            status="failed",
            stage="failed",
            message="Repository indexing failed.",
            error="The repository could not be indexed. Check the URL and server logs.",
        )


@app.post("/api/indexing", response_model=IndexJobResponse, status_code=status.HTTP_202_ACCEPTED)
def start_indexing(request: IndexRequest) -> IndexJobResponse:
    try:
        repository_name = _validate_repository_url(request.repo_url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_repository_url", "message": str(exc)}) from exc

    with jobs_lock:
        if any(
            job.repository_name == repository_name and job.status in {"queued", "running"}
            for job in jobs.values()
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "indexing_in_progress", "message": "This repository is already being indexed."},
            )
        job_id = uuid.uuid4().hex
        jobs[job_id] = IndexJobResponse(
            job_id=job_id,
            status="queued",
            stage="queued",
            message="Indexing queued.",
            repository_name=repository_name,
            updated_at=datetime.now(timezone.utc),
            completed_stages=[],
        )

    threading.Thread(target=_index_in_background, args=(job_id, request.repo_url), daemon=True).start()
    return jobs[job_id]


@app.get("/api/indexing/{job_id}", response_model=IndexJobResponse)
def indexing_status(job_id: str) -> IndexJobResponse:
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "job_not_found", "message": "The indexing job was not found."},
        )
    return job


def _sse_message(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@app.get("/api/questions/stream")
def stream_question(
    repository_name: str = Query(min_length=1, max_length=255),
    question: str = Query(min_length=1, max_length=4000),
) -> StreamingResponse:
    events: queue.Queue[dict[str, Any] | None] = queue.Queue()

    def run() -> None:
        try:
            result = _run_question(
                QuestionRequest(repository_name=repository_name, question=question),
                event_callback=events.put,
            )
            events.put({"type": "complete", "response": QuestionResponse(
                repository_name=repository_name,
                question=question,
                answer=result["answer"],
                document_count=result["document_count"],
                relevance_grade=result["relevance_grade"],
                retry_count=result["retry_count"],
                evidence=result["evidence"],
            ).model_dump(mode="json")})
        except ValueError as exc:
            events.put({"type": "error", "code": "repository_not_indexed", "message": str(exc)})
        except RuntimeError:
            events.put({"type": "error", "code": "service_configuration_error", "message": "The answer service is not configured."})
        except Exception:
            events.put({"type": "error", "code": "workflow_failed", "message": "The repository question could not be answered."})
        finally:
            events.put(None)

    threading.Thread(target=run, daemon=True).start()

    def generate():
        yield _sse_message({"type": "stage", "stage": "question_received", "status": "running", "message": "Submitting question."})
        while True:
            event = events.get()
            if event is None:
                break
            yield _sse_message(event)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post(
    "/api/questions",
    response_model=QuestionResponse,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def ask_question(request: QuestionRequest) -> QuestionResponse:
    try:
        result = _run_question(request)
    except ValueError as exc:
        if str(exc) == "repository_not_indexed":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "repository_not_indexed", "message": "The selected repository has not been indexed."},
            ) from exc
        raise
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "service_configuration_error", "message": str(exc)},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "workflow_failed", "message": "The repository question could not be answered."},
        ) from exc

    return QuestionResponse(
        repository_name=request.repository_name,
        question=request.question,
        answer=result["answer"],
        document_count=result["document_count"],
        relevance_grade=result["relevance_grade"],
        retry_count=result["retry_count"],
        evidence=result["evidence"],
    )
