import re
import threading
import uuid
import json
import queue
import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.embedder import Embedder
from app.langchain_llm import RepoPilotLLM
from app.langchain_retriever import RepoPilotRetriever
from app.graph import RepoPilotGraph
from app.reranker import Reranker
from app.vector_store import VectorStore
from app.indexing_service import index_repository
from app.auth import (
    clear_session_cookies,
    get_current_user,
    public_user,
    require_csrf,
    require_same_origin,
    set_session_cookies,
    verify_google_credential,
)
from app.database import SessionLocal, get_db
from app.db_models import Repository, User


class HealthResponse(BaseModel):
    status: str


class GoogleAuthRequest(BaseModel):
    credential: str = Field(min_length=1, max_length=10000)


class UserResponse(BaseModel):
    id: str
    email: str
    name: str | None = None
    picture_url: str | None = None
    is_active: bool


class AuthResponse(BaseModel):
    user: UserResponse


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
job_owners: dict[str, uuid.UUID] = {}
jobs_lock = threading.Lock()
INDEX_STAGES = ["cloning", "analyzing", "reading", "chunking", "embedding", "storing"]
logger = logging.getLogger(__name__)


app = FastAPI(title="RepoPilot API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_auth_browser_headers(request: Request, call_next: Any) -> Response:
    response = await call_next(request)
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
    return response


@app.post("/api/auth/google", response_model=AuthResponse)
def google_login(
    payload: GoogleAuthRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    require_same_origin(request)
    try:
        claims = verify_google_credential(payload.credential)
    except (RuntimeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_google_credential", "message": "Google sign-in could not be verified."},
        ) from None

    google_sub = str(claims["sub"])
    user = db.scalar(select(User).where(User.google_sub == google_sub))
    if user is None:
        user = User(
            google_sub=google_sub,
            email=str(claims["email"]),
            name=claims.get("name"),
            picture_url=claims.get("picture"),
            is_active=True,
        )
        db.add(user)
    elif not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "inactive_account", "message": "This account is inactive."},
        )
    else:
        user.email = str(claims["email"])
        user.name = claims.get("name")
        user.picture_url = claims.get("picture")
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "account_conflict", "message": "This Google account could not be linked."},
        ) from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "database_unavailable", "message": "The account service is temporarily unavailable."},
        ) from None
    try:
        set_session_cookies(response, user)
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "auth_configuration_error", "message": "Authentication is not configured."},
        ) from None
    return AuthResponse(user=UserResponse(**public_user(user)))


@app.get("/api/auth/me", response_model=AuthResponse)
def auth_me(current_user: User = Depends(get_current_user)) -> AuthResponse:
    return AuthResponse(user=UserResponse(**public_user(current_user)))


@app.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> None:
    require_same_origin(request)
    require_csrf(request)
    clear_session_cookies(response)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/api/repositories", response_model=RepositoriesResponse)
def repositories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RepositoriesResponse:
    try:
        names = db.scalars(
            select(Repository.name)
            .where(
                Repository.user_id == current_user.id,
                Repository.indexing_status == "completed",
            )
            .order_by(Repository.name)
        ).all()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "vector_store_unavailable", "message": "The repository index is unavailable."},
        ) from exc

    return RepositoriesResponse(
        repositories=[RepositorySummary(name=name) for name in names]
    )


def _build_question_graph(repository_name: str, user_id: uuid.UUID, db: Session) -> RepoPilotGraph:
    owned_repository = db.scalar(
        select(Repository).where(
            Repository.user_id == user_id,
            Repository.name == repository_name,
            Repository.indexing_status == "completed",
        )
    )
    if owned_repository is None:
        raise ValueError("repository_not_indexed")
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
    user_id: uuid.UUID,
    db: Session,
    event_callback: Any = None,
) -> dict[str, Any]:
    return _build_question_graph(request.repository_name, user_id, db).run_with_state(
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


def _index_in_background(job_id: str, repo_url: str, user_id: uuid.UUID) -> None:
    db = SessionLocal()
    repository_name = repo_url.rstrip("/").split("/")[-1].removesuffix(".git")
    repository: Repository | None = None
    current_stage = "queued"
    try:
        repository = db.scalar(
            select(Repository).where(
                Repository.user_id == user_id,
                Repository.name == repository_name,
            )
        )
        if repository:
            repository.indexing_status = "running"
            db.commit()

        def progress(stage: str, message: str) -> None:
            nonlocal current_stage
            current_stage = stage
            _update_job(job_id, status="running", stage=stage, message=message)

        result = index_repository(repo_url, progress=progress)
        if repository:
            repository.indexing_status = "completed"
            repository.indexed_at = datetime.now(timezone.utc)
            db.commit()
        _update_job(
            job_id,
            status="completed",
            stage="complete",
            message="Repository indexing completed.",
            repository_name=result["repository_name"],
            chunk_count=result["chunk_count"],
            completed_stages=["cloning", "analyzing", "reading", "chunking", "embedding", "storing"],
        )
    except Exception as exc:
        logger.exception(
            "Repository indexing failed",
            extra={
                "job_id": job_id,
                "repository_name": repository_name,
                "stage": current_stage,
            },
        )
        db.rollback()
        repository = db.scalar(
            select(Repository).where(
                Repository.user_id == user_id,
                Repository.name == repository_name,
            )
        )
        if repository:
            repository.indexing_status = "failed"
            db.commit()
        _update_job(
            job_id,
            status="failed",
            stage=current_stage,
            message=f"Repository indexing failed during {current_stage}.",
            error=f"{current_stage.capitalize()} failed. Check backend logs for details.",
        )
    finally:
        db.close()


@app.post("/api/indexing", response_model=IndexJobResponse, status_code=status.HTTP_202_ACCEPTED)
def start_indexing(
    request: IndexRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IndexJobResponse:
    require_csrf(http_request)
    try:
        repository_name = _validate_repository_url(request.repo_url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_repository_url", "message": str(exc)}) from exc

    with jobs_lock:
        if any(
            job.repository_name == repository_name
            and job.status in {"queued", "running"}
            and job_owners.get(existing_job_id) == current_user.id
            for existing_job_id, job in jobs.items()
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "indexing_in_progress", "message": "This repository is already being indexed."},
            )
        job_id = uuid.uuid4().hex
        repository = db.scalar(
            select(Repository).where(
                Repository.user_id == current_user.id,
                Repository.github_url == request.repo_url,
            )
        )
        if repository is None:
            repository = Repository(
                user_id=current_user.id,
                name=repository_name,
                github_url=request.repo_url,
                indexing_status="queued",
            )
            db.add(repository)
        else:
            repository.indexing_status = "queued"
        db.commit()
        job_owners[job_id] = current_user.id
        jobs[job_id] = IndexJobResponse(
            job_id=job_id,
            status="queued",
            stage="queued",
            message="Indexing queued.",
            repository_name=repository_name,
            updated_at=datetime.now(timezone.utc),
            completed_stages=[],
        )

    threading.Thread(
        target=_index_in_background,
        args=(job_id, request.repo_url, current_user.id),
        daemon=True,
    ).start()
    return jobs[job_id]


@app.get("/api/indexing/{job_id}", response_model=IndexJobResponse)
def indexing_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
) -> IndexJobResponse:
    with jobs_lock:
        job = jobs.get(job_id)
    if not job or job_owners.get(job_id) != current_user.id:
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    events: queue.Queue[dict[str, Any] | None] = queue.Queue()

    def run() -> None:
        try:
            result = _run_question(
                QuestionRequest(repository_name=repository_name, question=question),
                current_user.id,
                db,
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
def ask_question(
    request: QuestionRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuestionResponse:
    require_csrf(http_request)
    try:
        result = _run_question(request, current_user.id, db)
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
