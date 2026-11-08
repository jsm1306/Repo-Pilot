from collections.abc import Callable
import logging
from pathlib import Path
import subprocess
from typing import Any

from app.analyzer import RepositoryAnalyzer
from app.code_reader import CodeReader
from app.environment import EnvironmentAnalyzer
from app.embedder import Embedder
from app.file_classifier import FileClassifier
from app.models import EnvironmentReport
from app.repository import RepositoryLoader
from app.structural_chunker import StructuralChunker
from app.technology import TechnologyDetector
from app.documentation_reader import DocumentationReader
from app.vector_store import VectorStore

ProgressCallback = Callable[[str, str], None]
logger = logging.getLogger(__name__)


def index_repository(
    repo_url: str,
    progress: ProgressCallback | None = None,
    destination: str = "repos",
    user_id: str | None = None,
    repository_id: str | None = None,
) -> dict[str, Any]:
    def report(stage: str, message: str) -> None:
        if progress:
            progress(stage, message)

    repository_name = repo_url.rstrip("/").split("/")[-1]
    if repository_name.endswith(".git"):
        repository_name = repository_name[:-4]
    if (user_id is None) != (repository_id is None):
        raise ValueError("Both user_id and repository_id are required for scoped indexing.")
    repo_root = Path(destination)
    if user_id is not None:
        repo_root = repo_root / str(user_id) / str(repository_id)
    repo_path = repo_root / repository_name

    report("cloning", "Preparing repository")
    if repo_path.exists():
        if not (repo_path / ".git").exists():
            raise RuntimeError("The destination exists but is not a Git repository.")
        remote = subprocess.check_output(
            ["git", "-C", str(repo_path), "config", "--get", "remote.origin.url"],
            text=True,
        ).strip().removesuffix(".git").rstrip("/")
        requested = repo_url.removesuffix(".git").rstrip("/")
        if remote and remote != requested:
            raise RuntimeError("A different repository already uses this local destination.")
        report("cloning", "Using the existing local clone")
    else:
        repo_path = RepositoryLoader(repo_url, destination=str(repo_root)).clone()

    report("analyzing", "Analyzing repository structure")
    report_data = RepositoryAnalyzer(repo_path).analyze()
    classifier = FileClassifier()
    detector = TechnologyDetector(repo_path)
    technologies = detector.detect()
    environment_analyzer = EnvironmentAnalyzer(repo_path)
    EnvironmentReport(
        environment_files=[str(path) for path in environment_analyzer.find_environment_files()],
        required_variables=environment_analyzer.find_environment_variables(),
        services=environment_analyzer.find_services(),
    )
    report_data.languages = technologies["languages"]
    report_data.frameworks = technologies["frameworks"]
    report_data.databases = technologies["databases"]
    report_data.tools = technologies["tools"]
    report("reading", "Reading source files")
    reader = CodeReader(repo_path)
    source_files = reader.read_source_files()
    discovery_stats = reader.stats
    DocumentationReader(repo_path).read_documents()

    report("chunking", "Chunking source files")
    chunker = StructuralChunker()
    all_chunks = []
    files_with_zero_chunks = []
    for source_file in source_files:
        chunks = chunker.chunk_file(source_file["path"], source_file["content"])
        if not chunks:
            files_with_zero_chunks.append(source_file["path"])
        all_chunks.extend(chunks)

    stats = {
        **discovery_stats,
        "files_chunked": len(source_files) - len(files_with_zero_chunks),
        "files_with_zero_chunks": files_with_zero_chunks,
        "chunks_generated": len(all_chunks),
    }
    logger.info(
        "Repository indexing coverage: included=%d chunked=%d zero_chunks=%d chunks=%d",
        stats["files_included"],
        stats["files_chunked"],
        len(files_with_zero_chunks),
        stats["chunks_generated"],
    )

    if not all_chunks:
        raise RuntimeError("No supported source files were found in the repository.")

    report("embedding", "Embedding source chunks")
    embeddings = Embedder().embed([chunk.content for chunk in all_chunks])
    report("storing", "Storing repository vectors")
    VectorStore().add_chunks(
        all_chunks,
        embeddings,
        repository_name,
        user_id=user_id,
        repository_id=repository_id,
    )
    return {
        "repository_name": repository_name,
        "chunk_count": len(all_chunks),
        "repository_path": str(repo_path),
        "indexing_stats": stats,
    }
