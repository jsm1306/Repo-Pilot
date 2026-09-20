from app.repository import RepositoryLoader
from app.analyzer import RepositoryAnalyzer
from app.technology import TechnologyDetector


def main():

    repo_url = input("Enter GitHub repository URL: ")

    loader = RepositoryLoader(repo_url)

    repo_path = loader.clone()

    analyzer = RepositoryAnalyzer(repo_path)
    report = analyzer.analyze()

    detector = TechnologyDetector(repo_path)
    technologies = detector.detect()

    report.languages = technologies["languages"]
    report.frameworks = technologies["frameworks"]
    report.databases = technologies["databases"]
    report.tools = technologies["tools"]

    print("\n--- Repository Report ---")

    print(f"Repository: {report.repository_name}")
    print(f"Files: {report.file_count}")
    print(f"Directories: {report.directory_count}")

    print(f"\nLanguages: {report.languages}")
    print(f"Frameworks: {report.frameworks}")
    print(f"Databases: {report.databases}")
    print(f"Tools: {report.tools}")

    print("\nFiles:")

    for file in report.files:
        print(f"  {file}")


if __name__ == "__main__":
    main()