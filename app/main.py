from app.repository import RepositoryLoader
from app.analyzer import RepositoryAnalyzer
from app.technology import TechnologyDetector
from app.file_classifier import FileClassifier
from app.environment import EnvironmentAnalyzer
from app.models import EnvironmentReport
from app.code_reader import CodeReader
from app.documentation_reader import DocumentationReader
from app.chunker import CodeChunker
from app.embedder import Embedder
def main():

    repo_url = input("Enter GitHub repository URL: ")

    loader = RepositoryLoader(repo_url)

    repo_path = loader.clone()

    analyzer = RepositoryAnalyzer(repo_path)
    report = analyzer.analyze()

    classifier = FileClassifier()
    # print("\n--- File Classification ---")

    # for file in report.files:
    #     file_path = repo_path / file
    #     category = classifier.classify(file_path)
    #     print(f"{file:50} → {category}")

    detector = TechnologyDetector(repo_path)
    technologies = detector.detect()
    environment_analyzer = EnvironmentAnalyzer(repo_path)
    # print("\nEnvironment files:")
    # print(environment_analyzer.find_environment_files())

    # print("\nEnvironment variables:")
    # print(environment_analyzer.find_environment_variables())

    environment_analyzer = EnvironmentAnalyzer(repo_path)
    environment_report = EnvironmentReport(
        environment_files=[
            str(path)
            for path in environment_analyzer.find_environment_files()
        ],
        required_variables=environment_analyzer.find_environment_variables(),
        services=environment_analyzer.find_services(),
    )
    # print("\nEnvironment Report")
    # print("------------------")

    # print("Environment files:")
    # for file in environment_report.environment_files:
    #     print(f"  - {file}")

    # print("\nRequired variables:")
    # for variable in environment_report.required_variables:
    #     print(f"  - {variable}")

    # print("\nServices:")
    # for service in environment_report.services:
    #     print(f"  - {service}")
    reader = CodeReader(repo_path)

    source_files = reader.read_source_files()

    # print("\nSource files:")
    # for file in source_files:
    #     print(f"  - {file['path']}")

    report.languages = technologies["languages"]
    report.frameworks = technologies["frameworks"]
    report.databases = technologies["databases"]
    report.tools = technologies["tools"]

    documentation_reader = DocumentationReader(repo_path)

    documents = documentation_reader.read_documents()

    # print("\nDocumentation files:")

    # for document in documents:
    #     print(f"  - {document['path']}")
    chunker = CodeChunker(
    chunk_size=50,
    overlap=10
    )

    print("\nCode chunks:")

    for file in source_files:

        chunks = chunker.chunk_file(
            file["path"],
            file["content"]
        )

        # print(
        #     f"\n{file['path']} → "
        #     f"{len(chunks)} chunks"
        # )

        # for chunk in chunks[:2]:
        #     print(
        #         f"  Lines {chunk.start_line}-"
        #         f"{chunk.end_line}"
        #     )

    embedder = Embedder()

    texts = []

    for file in source_files:

        chunks = chunker.chunk_file(
            file["path"],
            file["content"]
        )

        for chunk in chunks:
            texts.append(chunk.content)

    embeddings = embedder.embed(texts)

    print("\nEmbedding information:")
    print("Number of chunks:", len(texts))
    print("Embedding shape:", embeddings.shape)


if __name__ == "__main__":
    main()