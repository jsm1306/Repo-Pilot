from app.repository import RepositoryLoader
from app.analyzer import RepositoryAnalyzer
from app.technology import TechnologyDetector
from app.file_classifier import FileClassifier
from app.environment import EnvironmentAnalyzer
from app.models import EnvironmentReport
from app.code_reader import CodeReader
from app.documentation_reader import DocumentationReader
from app.structural_chunker import StructuralChunker
from app.embedder import Embedder
from app.vector_store import VectorStore
from app.reranker import Reranker
from app.langchain_llm import RepoPilotLLM
from app.langchain_retriever import RepoPilotRetriever
from app.tool_agent import RepoPilotToolAgent
from app.graph import RepoPilotGraph

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
    chunker=StructuralChunker()
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

    query = input("\nAsk RepoPilot: ")
    embedder = Embedder()
    reranker = Reranker()

    retriever = RepoPilotRetriever(
        embedder=embedder,
        vector_store=vector_store,
        reranker=reranker,
        repository_name=repository_name
    )

    llm = RepoPilotLLM()
    graph = RepoPilotGraph(retriever=retriever, llm=llm)

    try:
        answer = graph.run(query)
        print("\nRepoPilot:\n")
        print(answer)
    except Exception as e:
        print(f"\nRepoPilot failed: {type(e).__name__}: {e}")


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