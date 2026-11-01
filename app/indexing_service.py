from collections.abc import Callable
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


def index_repository(
    repo_url: str,
    progress: ProgressCallback | None = None,
    destination: str = "repos",
) -> dict[str, Any]:
    def report(stage: str, message: str) -> None:
        if progress:
            progress(stage, message)

    repository_name = repo_url.rstrip("/").split("/")[-1]
    if repository_name.endswith(".git"):
        repository_name = repository_name[:-4]
    repo_path = Path(destination) / repository_name

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
        repo_path = RepositoryLoader(repo_url, destination=destination).clone()

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
    source_files = CodeReader(repo_path).read_source_files()
    DocumentationReader(repo_path).read_documents()

    report("chunking", "Chunking source files")
    chunker = StructuralChunker()
    all_chunks = []
    for source_file in source_files:
        all_chunks.extend(chunker.chunk_file(source_file["path"], source_file["content"]))

    if not all_chunks:
        raise RuntimeError("No supported source files were found in the repository.")

    report("embedding", "Embedding source chunks")
    embeddings = Embedder().embed([chunk.content for chunk in all_chunks])
    report("storing", "Storing repository vectors")
    VectorStore().add_chunks(all_chunks, embeddings, repository_name)
    return {"repository_name": repository_name, "chunk_count": len(all_chunks)}
