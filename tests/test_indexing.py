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


def test_code_and_markdown_files_are_collected(tmp_path):
    (tmp_path / "app.py").write_text("print('hello')", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Guide", encoding="utf-8")

    files = CodeReader(str(tmp_path)).read_source_files()

    assert {item["path"] for item in files} == {"app.py", "README.md"}


def test_repository_with_no_supported_files_fails_clearly(monkeypatch, tmp_path):
    destination = tmp_path / "repos"

    class Loader:
        def __init__(self, repo_url, destination):
            self.destination = Path(destination)

        def clone(self):
            repo_path = self.destination / "empty"
            (repo_path / ".git").mkdir(parents=True)
            (repo_path / "config.json").write_text("{}", encoding="utf-8")
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
