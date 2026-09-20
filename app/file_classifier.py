from pathlib import Path


class FileClassifier:

    SOURCE_EXTENSIONS = {
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

    DOCUMENTATION_EXTENSIONS = {
        ".md",
        ".txt",
        ".rst",
    }

    CONFIGURATION_FILES = {
        "dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        ".gitignore",
        ".env.example",
    }

    DEPENDENCY_FILES = {
        "package-lock.json",
        "requirements.txt",
        "requirement.txt",
        "pyproject.toml",
        "package.json",
    }

    SECRET_FILES = {
        ".env",
        ".env.local",
        ".env.production",
        ".env.development",
    }

    DATA_EXTENSIONS = {
        ".csv",
        ".json",
        ".sqlite",
        ".sqlite3",
        ".db",
    }

    ASSET_EXTENSIONS = {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".svg",
        ".ico",
        ".mp4",
        ".mp3",
        ".pdf",
    }

    def classify(self, file_path: Path) -> str:

        filename = file_path.name.lower()
        extension = file_path.suffix.lower()

        if filename in self.SECRET_FILES:
            return "secret"

        if filename in self.DEPENDENCY_FILES:
            return "dependency"

        if filename in self.CONFIGURATION_FILES:
            return "configuration"

        if extension in self.SOURCE_EXTENSIONS:
            return "source"

        if extension in self.DOCUMENTATION_EXTENSIONS:
            return "documentation"

        if extension in self.DATA_EXTENSIONS:
            return "data"

        if extension in self.ASSET_EXTENSIONS:
            return "asset"

        return "unknown"
