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
from app.indexing_service import index_repository as run_indexing

def index_repository():
    repo_url=input("Enter GitHub repository URL: ")
    result = run_indexing(repo_url)
    print("Stored chunks:", result["chunk_count"])

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