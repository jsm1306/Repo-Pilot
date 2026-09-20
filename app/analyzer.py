from pathlib import Path
from app.models import RepositoryReport
IGNORED_DIRECTORIES = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
}

class RepositoryAnalyzer:

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)

    def analyze(self):
        files = []
        directories = []

        for path in self.repo_path.rglob("*"):
            if any(part in IGNORED_DIRECTORIES for part in path.parts):
                continue
            if path.is_file():
                files.append(path)
            elif path.is_dir():
                directories.append(path)

        return RepositoryReport(
            repository_name=self.repo_path.name,
            file_count=len(files),
            directory_count=len(directories),
            files=[str(file.relative_to(self.repo_path)) for file in files],
            directories=[
                str(directory.relative_to(self.repo_path))
                for directory in directories
            ]
        )