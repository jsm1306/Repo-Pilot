from pathlib import Path
import subprocess


class RepositoryLoader:

    def __init__(self, repo_url: str, destination: str = "repos"):
        self.repo_url = repo_url
        self.destination = Path(destination)

    def clone(self):
        self.destination.mkdir(parents=True, exist_ok=True)

        repository_name = self.repo_url.rstrip("/").split("/")[-1]
        if repository_name.endswith(".git"):
            repository_name = repository_name[:-4]

        repo_path = self.destination / repository_name

        subprocess.run(
            ["git", "clone", self.repo_url, str(repo_path)],
            check=True
        )

        return repo_path