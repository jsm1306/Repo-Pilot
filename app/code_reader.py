from pathlib import Path


class CodeReader:

    SUPPORTED_EXTENSIONS = {
        ".py",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".java",
        ".cpp",
        ".c",
        ".go",
        ".rs",
        ".php",
        ".rb",
        ".html",
        ".css",
    }

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)

    def read_source_files(self):
        source_files = []

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

            source_files.append({
                "path": str(path.relative_to(self.repo_path)),
                "content": content,
            })

        return source_files