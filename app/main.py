from app.repository import RepositoryLoader
from app.analyzer import RepositoryAnalyzer
from app.technology import TechnologyDetector
from app.file_classifier import FileClassifier
from app.environment import EnvironmentAnalyzer
from app.models import EnvironmentReport

def main():

    repo_url = input("Enter GitHub repository URL: ")

    loader = RepositoryLoader(repo_url)

    repo_path = loader.clone()

    analyzer = RepositoryAnalyzer(repo_path)
    report = analyzer.analyze()

    classifier = FileClassifier()
    print("\n--- File Classification ---")

    for file in report.files:
        file_path = repo_path / file
        category = classifier.classify(file_path)
        print(f"{file:50} → {category}")

    detector = TechnologyDetector(repo_path)
    technologies = detector.detect()
    environment_analyzer = EnvironmentAnalyzer(repo_path)
    print("\nEnvironment files:")
    print(environment_analyzer.find_environment_files())

    print("\nEnvironment variables:")
    print(environment_analyzer.find_environment_variables())

    environment_analyzer = EnvironmentAnalyzer(repo_path)
    environment_report = EnvironmentReport(
        environment_files=[
            str(path)
            for path in environment_analyzer.find_environment_files()
        ],
        required_variables=environment_analyzer.find_environment_variables(),
        services=environment_analyzer.find_services(),
    )
    print("\nEnvironment Report")
    print("------------------")

    print("Environment files:")
    for file in environment_report.environment_files:
        print(f"  - {file}")

    print("\nRequired variables:")
    for variable in environment_report.required_variables:
        print(f"  - {variable}")

    print("\nServices:")
    for service in environment_report.services:
        print(f"  - {service}")

    report.languages = technologies["languages"]
    report.frameworks = technologies["frameworks"]
    report.databases = technologies["databases"]
    report.tools = technologies["tools"]

    # print("\n--- Repository Report ---")

    # print(f"Repository: {report.repository_name}")
    # print(f"Files: {report.file_count}")
    # print(f"Directories: {report.directory_count}")

    # print(f"\nLanguages: {report.languages}")
    # print(f"Frameworks: {report.frameworks}")
    # print(f"Databases: {report.databases}")
    # print(f"Tools: {report.tools}")

    # print("\nFiles:")

    # for file in report.files:
    #     print(f"  {file}")


if __name__ == "__main__":
    main()