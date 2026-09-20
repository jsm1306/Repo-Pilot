from pathlib import Path


class EnvironmentAnalyzer:

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
    def find_environment_files(self):
        environment_files = []

        for path in self.repo_path.rglob("*"):

            if not path.is_file():
                continue

            if ".git" in path.parts:
                continue

            filename = path.name.lower()

            if filename in {
                ".env",
                ".env.example",
                ".env.local",
                ".env.development",
                ".env.production",
            }:
                environment_files.append(
                    path.relative_to(self.repo_path)
                )

        return environment_files

    def find_environment_variables(self):
        variables = set()

        environment_files = {
            ".env",
            ".env.example",
            ".env.local",
            ".env.development",
            ".env.production",
        }

        for path in self.repo_path.rglob("*"):

            if not path.is_file():
                continue

            if ".git" in path.parts:
                continue

            if path.name.lower() in environment_files:

                try:
                    content = path.read_text(
                        encoding="utf-8",
                        errors="ignore"
                    )
                except Exception:
                    continue

                for line in content.splitlines():

                    line = line.strip()

                    # Ignore comments and empty lines
                    if not line or line.startswith("#"):
                        continue

                    # Environment variables normally look like:
                    # KEY=value
                    if "=" in line:
                        variable = line.split("=", 1)[0].strip()

                        if variable:
                            variables.add(variable)

        return sorted(variables)
    def find_services(self):
        services = []

        compose_files = [
            self.repo_path / "docker-compose.yml",
            self.repo_path / "docker-compose.yaml",
        ]

        for compose_file in compose_files:

            if not compose_file.exists():
                continue

            try:
                content = compose_file.read_text(
                    encoding="utf-8",
                    errors="ignore"
                )
            except Exception:
                continue

            inside_services = False

            for line in content.splitlines():

                stripped = line.strip()

                if stripped == "services:":
                    inside_services = True
                    continue

                if inside_services:

                    # Stop when another top-level YAML section begins
                    if line and not line.startswith((" ", "\t")):
                        break

                    if line.startswith("  ") and not line.startswith("    "):
                        service_name = stripped.rstrip(":")

                        if service_name:
                            services.append(service_name)

        return services