from pathlib import Path

import pytest

from app.code_reader import CodeReader
from app.structural_chunker import StructuralChunker
from app import indexing_service


def test_readme_only_repository_is_indexed(monkeypatch, tmp_path):
    destination = tmp_path / "repos"
    captured = {}

    class Loader:
        def __init__(self, repo_url, destination):
            self.destination = Path(destination)

        def clone(self):
            repo_path = self.destination / "readme-only"
            (repo_path / ".git").mkdir(parents=True)
            (repo_path / "README.md").write_text("# RepoPilot\n\nUseful documentation.", encoding="utf-8")
            return repo_path

    class Embedder:
        def embed(self, texts):
            captured["embedded"] = texts
            return _Embeddings(len(texts))

    class VectorStore:
        def add_chunks(self, chunks, embeddings, repository_name, **scope):
            captured["stored"] = (chunks, embeddings, repository_name, scope)

    _patch_analysis_dependencies(monkeypatch)
    monkeypatch.setattr(indexing_service, "RepositoryLoader", Loader)
    monkeypatch.setattr(indexing_service, "Embedder", Embedder)
    monkeypatch.setattr(indexing_service, "VectorStore", VectorStore)

    result = indexing_service.index_repository(
        "https://github.com/example/readme-only",
        destination=str(destination),
        user_id="user-a",
        repository_id="repo-a",
    )

    assert result["repository_name"] == "readme-only"
    assert result["chunk_count"] == 1
    assert Path(result["repository_path"]).parts[-3:] == ("user-a", "repo-a", "readme-only")
    assert captured["embedded"] == ["# RepoPilot\n\nUseful documentation."]
    assert captured["stored"][2] == "readme-only"
    assert captured["stored"][3] == {"user_id": "user-a", "repository_id": "repo-a"}
    assert captured["stored"][0][0].file_path == "README.md"
    assert result["indexing_stats"]["files_included"] == 1
    assert result["indexing_stats"]["chunks_generated"] == 1


def test_code_and_markdown_files_are_collected(tmp_path):
    (tmp_path / "app.py").write_text("print('hello')", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Guide", encoding="utf-8")

    files = CodeReader(str(tmp_path)).read_source_files()

    assert {item["path"] for item in files} == {"app.py", "README.md"}


@pytest.mark.parametrize("filename", ["Dockerfile", "Jenkinsfile", "Makefile"])
def test_extensionless_build_files_are_collected(tmp_path, filename):
    (tmp_path / filename).write_text("FROM python:3.13\n", encoding="utf-8")

    files = CodeReader(str(tmp_path)).read_source_files()

    assert [item["path"] for item in files] == [filename]


def test_configuration_and_workflow_files_are_collected(tmp_path):
    (tmp_path / ".dockerignore").write_text("node_modules\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(".venv\n", encoding="utf-8")
    (tmp_path / "docker-compose.yml").write_text("services:\n  api:\n    build: .\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("fastapi\n", encoding="utf-8")
    workflow = tmp_path / ".github" / "workflows"
    workflow.mkdir(parents=True)
    (workflow / "ci.yml").write_text("name: CI\n", encoding="utf-8")

    reader = CodeReader(str(tmp_path))
    files = reader.read_source_files()

    assert {item["path"].replace("\\", "/") for item in files} == {
        ".dockerignore",
        ".gitignore",
        "docker-compose.yml",
        "requirements.txt",
        ".github/workflows/ci.yml",
    }


def test_exclusions_report_meaningful_reasons(tmp_path):
    (tmp_path / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
    (tmp_path / ".env.production.local").write_text("TOKEN=secret\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("TOKEN=replace-me\n", encoding="utf-8")
    (tmp_path / "app.pyc").write_bytes(b"\x00\x01")
    ignored = tmp_path / "node_modules"
    ignored.mkdir()
    (ignored / "package.js").write_text("ignored", encoding="utf-8")

    reader = CodeReader(str(tmp_path))
    files = reader.read_source_files()
    assert [item["path"] for item in files] == [".env.example"]
    reasons = {
        item["path"].replace("\\", "/"): item["reason"]
        for item in reader.stats["excluded_files"]
    }

    assert reasons[".env"] == "secret_file"
    assert reasons["app.pyc"] == "generated_artifact"
    assert reader.stats["directories_pruned"] == 1


def test_procfile_chunks_process_declarations():
    chunks = StructuralChunker().chunk_file(
        "Procfile",
        "web: gunicorn app:app\nworker: celery -A app worker\nrelease: python manage.py migrate",
    )

    assert [chunk.symbol for chunk in chunks] == ["web", "worker", "release"]
    assert all(chunk.language == "procfile" for chunk in chunks)


def test_jenkinsfile_chunks_declarative_pipeline_boundaries():
    chunks = StructuralChunker().chunk_file(
        "Jenkinsfile",
        """pipeline {
  agent any
  stages {
    stage('Build') {
      steps {
        sh 'make build'
      }
    }
  }
}""",
    )

    assert [chunk.symbol for chunk in chunks] == ["pipeline", "stages", "stage('Build')", "steps"]
    assert all(chunk.language == "jenkinsfile" for chunk in chunks)
    assert "sh 'make build'" in chunks[-1].content


def test_structural_chunker_preserves_configuration_file_types():
    chunker = StructuralChunker()

    docker_chunks = chunker.chunk_file("Dockerfile", "FROM python:3.13\nWORKDIR /app\nCOPY . .")
    yaml_chunks = chunker.chunk_file("docker-compose.yml", "services:\n  api:\n    build: .")

    assert docker_chunks
    assert docker_chunks[0].language == "dockerfile"
    assert yaml_chunks
    assert yaml_chunks[0].language == "yaml"


def test_repository_with_no_supported_files_fails_clearly(monkeypatch, tmp_path):
    destination = tmp_path / "repos"

    class Loader:
        def __init__(self, repo_url, destination):
            self.destination = Path(destination)

        def clone(self):
            repo_path = self.destination / "empty"
            (repo_path / ".git").mkdir(parents=True)
            (repo_path / "image.png").write_bytes(b"\x89PNG")
            return repo_path

    _patch_analysis_dependencies(monkeypatch)
    monkeypatch.setattr(indexing_service, "RepositoryLoader", Loader)

    with pytest.raises(RuntimeError, match="No supported source files"):
        indexing_service.index_repository(
            "https://github.com/example/empty",
            destination=str(destination),
        )


def test_markdown_chunks_preserve_headings_and_metadata():
    chunks = StructuralChunker().chunk_file(
        "docs/guide.md",
        "# Introduction\n\nIntro text.\n\n## Installation\n\nRun the command.",
    )

    assert [chunk.symbol for chunk in chunks] == ["Introduction", "Installation"]
    assert all(chunk.file_path == "docs/guide.md" for chunk in chunks)
    assert all(chunk.language == "markdown" for chunk in chunks)
    assert all(chunk.symbol_type == "heading" for chunk in chunks)
    assert chunks[0].start_line == 1
    assert chunks[1].start_line == 5


class _Embeddings:
    def __init__(self, count):
        self.count = count

    def tolist(self):
        return [[0.0] for _ in range(self.count)]


def _patch_analysis_dependencies(monkeypatch):
    class Report:
        languages = []
        frameworks = []
        databases = []
        tools = []

    class Analyzer:
        def __init__(self, repo_path):
            pass

        def analyze(self):
            return Report()

    class Detector:
        def __init__(self, repo_path):
            pass

        def detect(self):
            return {"languages": [], "frameworks": [], "databases": [], "tools": []}

    class Environment:
        def __init__(self, repo_path):
            pass

        def find_environment_files(self):
            return []

        def find_environment_variables(self):
            return []

        def find_services(self):
            return []

    class Documentation:
        def __init__(self, repo_path):
            pass

        def read_documents(self):
            return []

    monkeypatch.setattr(indexing_service, "RepositoryAnalyzer", Analyzer)
    monkeypatch.setattr(indexing_service, "TechnologyDetector", Detector)
    monkeypatch.setattr(indexing_service, "EnvironmentAnalyzer", Environment)
    monkeypatch.setattr(indexing_service, "DocumentationReader", Documentation)
