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
from app.vector_store import VectorStore

def index_repository():
    repo_url=input("Enter GitHub repository URL: ")
    loader=RepositoryLoader(repo_url)
    repo_path=loader.clone()
    repository_name=repo_path.name
    analyzer=RepositoryAnalyzer(repo_path)
    report=analyzer.analyze()
    classifier=FileClassifier()
    detector=TechnologyDetector(repo_path)
    technologies=detector.detect()
    environment_analyzer=EnvironmentAnalyzer(repo_path)
    environment_report=EnvironmentReport(
        environment_files=[str(path) for path in environment_analyzer.find_environment_files()],
        required_variables=environment_analyzer.find_environment_variables(),
        services=environment_analyzer.find_services(),
    )
    reader=CodeReader(repo_path)
    source_files=reader.read_source_files()
    report.languages=technologies["languages"]
    report.frameworks=technologies["frameworks"]
    report.databases=technologies["databases"]
    report.tools=technologies["tools"]
    documentation_reader=DocumentationReader(repo_path)
    documents=documentation_reader.read_documents()
    chunker=CodeChunker(chunk_size=50,overlap=10)
    embedder=Embedder()
    all_chunks=[]
    texts=[]
    for file in source_files:
        chunks=chunker.chunk_file(file["path"],file["content"])
        all_chunks.extend(chunks)
        for chunk in chunks:
            texts.append(chunk.content)
    embeddings=embedder.embed(texts)
    vector_store=VectorStore()
    vector_store.add_chunks(all_chunks,embeddings, repository_name)
    print("Stored chunks:",len(all_chunks))

def search_repository():
    embedder=Embedder()
    vector_store=VectorStore()
    repositories=vector_store.get_repositories()

    if not repositories:
        print("\nNo repositories have been indexed yet.")
        return

    print("\nIndexed repositories:")
    for i,repository in enumerate(repositories,start=1):
        print(f"{i}. {repository}")

    choice=input("\nSelect repository: ")

    try:
        repository_name=repositories[int(choice)-1]
    except (ValueError,IndexError):
        print("\nInvalid repository selection.")
        return

    query=input("\nAsk RepoPilot: ")
    query_embedding=embedder.embed([query])[0]
    results=vector_store.search(query_embedding,repository_name,n_results=5)

    if not results["documents"][0]:
        print(f"\nNo relevant code found in {repository_name}.")
        return

    print("\nRelevant code:")
    for i,document in enumerate(results["documents"][0],start=1):
        metadata=results["metadatas"][0][i-1]
        print(f"\n{i}. {metadata['file_path']} (lines {metadata['start_line']}-{metadata['end_line']})")
        print(document[:500])

def main():
    print("\nRepoPilot")
    print("1. Index repository")
    print("2. Search repository")
    choice=input("\nChoose an option: ")
    if choice=="1":
        index_repository()
    elif choice=="2":
        search_repository()
    else:
        print("Invalid choice.")

if __name__=="__main__":
    main()