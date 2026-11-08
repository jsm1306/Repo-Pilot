import logging
import os
from pathlib import Path
from typing import Any

from app.file_classifier import FileClassifier

logger = logging.getLogger(__name__)

IGNORED_DIRECTORIES = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
    "coverage",
    "target",
}

GENERATED_SUFFIXES = {".map", ".pyc", ".pyo", ".lockb"}


class CodeReader:
    """Discover readable, relevant repository files for indexing."""

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.classifier = FileClassifier()
        self.stats: dict[str, Any] = {
            "files_discovered": 0,
            "files_included": 0,
            "files_excluded": 0,
            "exclusion_reasons": {},
            "included_files": [],
            "excluded_files": [],
            "directories_pruned": 0,
        }

    def _exclude(self, path: Path, reason: str) -> None:
        self.stats["files_excluded"] += 1
        self.stats["exclusion_reasons"][reason] = (
            self.stats["exclusion_reasons"].get(reason, 0) + 1
        )
        self.stats["excluded_files"].append(
            {"path": str(path.relative_to(self.repo_path)), "reason": reason}
        )

    def read_source_files(self) -> list[dict[str, str]]:
        source_files = []

        for root, directories, filenames in os.walk(self.repo_path, topdown=True):
            ignored = [name for name in directories if name in IGNORED_DIRECTORIES]
            for name in ignored:
                directories.remove(name)
            self.stats["directories_pruned"] += len(ignored)

            for filename in filenames:
                path = Path(root) / filename
                self.stats["files_discovered"] += 1
                relative_path = path.relative_to(self.repo_path)

                filename = path.name.lower()
                if self.classifier.is_secret_file(path):
                    self._exclude(path, "secret_file")
                    continue

                if path.suffix.lower() in GENERATED_SUFFIXES or filename.endswith(".min.js"):
                    self._exclude(path, "generated_artifact")
                    continue

                if not self.classifier.is_indexable(path):
                    self._exclude(path, "unsupported_file_type")
                    continue

                try:
                    content = path.read_text(encoding="utf-8", errors="strict")
                except UnicodeDecodeError:
                    self._exclude(path, "binary_or_non_utf8")
                    continue
                except OSError:
                    self._exclude(path, "unreadable")
                    continue

                if "\x00" in content:
                    self._exclude(path, "binary_file")
                    continue

                source_files.append({"path": str(relative_path), "content": content})
                self.stats["files_included"] += 1
                self.stats["included_files"].append(str(relative_path))

        logger.info(
            "Repository file discovery: discovered=%d included=%d excluded=%d pruned_directories=%d reasons=%s",
            self.stats["files_discovered"],
            self.stats["files_included"],
            self.stats["files_excluded"],
            self.stats["directories_pruned"],
            self.stats["exclusion_reasons"],
        )
        return source_files
