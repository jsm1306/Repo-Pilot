from pathlib import Path
import re


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
        "containerfile",
        "jenkinsfile",
        "makefile",
        "procfile",
        "justfile",
        "vagrantfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        ".dockerignore",
        ".gitignore",
        ".gitattributes",
        ".env.example",
        ".env.sample",
        ".env.template",
        "nginx.conf",
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
    SAFE_TEMPLATE_FILES = {".env.example", ".env.sample", ".env.template"}

    DATA_EXTENSIONS = {
        ".csv",
        ".json",
        ".sqlite",
        ".sqlite3",
        ".db",
    }

    CONFIGURATION_EXTENSIONS = {
        ".conf",
        ".ini",
        ".json",
        ".toml",
        ".yaml",
        ".yml",
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

        if self.is_secret_file(file_path):
            return "secret"

        if filename in self.DEPENDENCY_FILES:
            return "dependency"

        if filename in self.CONFIGURATION_FILES:
            return "configuration"

        if extension in self.SOURCE_EXTENSIONS:
            return "source"

        if extension in self.CONFIGURATION_EXTENSIONS:
            return "configuration"

        if extension in self.DOCUMENTATION_EXTENSIONS:
            return "documentation"

        if extension in self.DATA_EXTENSIONS:
            return "data"

        if extension in self.ASSET_EXTENSIONS:
            return "asset"

        return "unknown"

    def is_secret_file(self, file_path: Path) -> bool:
        filename = file_path.name.lower()
        if filename in self.SAFE_TEMPLATE_FILES:
            return False
        return filename in self.SECRET_FILES or bool(re.fullmatch(r"\.env\..+", filename))

    def is_indexable(self, file_path: Path) -> bool:
        return self.classify(file_path) in {
            "source",
            "documentation",
            "configuration",
            "dependency",
        }
