from dataclasses import dataclass, field


@dataclass
class RepositoryReport:
    repository_name: str
    file_count: int
    directory_count: int

    files: list[str] = field(default_factory=list)
    directories: list[str] = field(default_factory=list)

    languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    databases: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
@dataclass
class EnvironmentReport:
    environment_files: list[str] = field(default_factory=list)
    required_variables: list[str] = field(default_factory=list)
    missing_variables: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)