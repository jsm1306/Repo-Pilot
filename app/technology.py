from pathlib import Path


class TechnologyDetector:

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)

    def detect(self):

        technologies = {
            "languages": [],
            "frameworks": [],
            "databases": [],
            "tools": []
        }

        # Python
        python_files = list(self.repo_path.rglob("*.py"))

        if python_files:
            technologies["languages"].append("Python")

        # JavaScript
        javascript_files = list(self.repo_path.rglob("*.js"))

        if javascript_files:
            technologies["languages"].append("JavaScript")

        # TypeScript
        typescript_files = list(self.repo_path.rglob("*.ts"))

        if typescript_files:
            technologies["languages"].append("TypeScript")

        # Django
        if (self.repo_path / "manage.py").exists():
            technologies["frameworks"].append("Django")

        # Node.js
        if (self.repo_path / "package.json").exists():
            technologies["tools"].append("Node.js")

        # SQLite
        sqlite_files = list(self.repo_path.rglob("*.sqlite3"))

        if sqlite_files:
            technologies["databases"].append("SQLite")

        return technologies