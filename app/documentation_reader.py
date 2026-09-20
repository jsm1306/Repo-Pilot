from pathlib import Path


class DocumentationReader:

    SUPPORTED_EXTENSIONS = {
        ".md",
        ".txt",
        ".rst",
    }

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)

    def read_documents(self):
        documents = []

        for path in self.repo_path.rglob("*"):

            if not path.is_file():
                continue

            if ".git" in path.parts:
                continue

            if any(
                ignored in path.parts
                for ignored in {
                    "node_modules",
                    "__pycache__",
                    ".venv",
                    "venv",
                    "dist",
                    "build",
                }
            ):
                continue

            if path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
                continue

            try:
                content = path.read_text(
                    encoding="utf-8",
                    errors="ignore"
                )
            except Exception:
                continue

            documents.append({
                "path": str(path.relative_to(self.repo_path)),
                "content": content,
            })

        return documents