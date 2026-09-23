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
from app.llm import GroqLLM

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
    results=vector_store.search(query_embedding,repository_name,n_results=10)
    documents=results["documents"][0]
    metadatas=results["metadatas"][0]

    if not results["documents"][0]:
        print(f"\nNo relevant code found in {repository_name}.")
        return
    # My understanding: Reranks the most genuine relevant docs or pieces of files based on the query
    reranker=Reranker()
    ranked=reranker.rerank(query,documents,metadatas,top_k=5)
    context_parts=[]

    for document,metadata,score in ranked:
        context_parts.append(
            f"""File: {metadata['file_path']}
    Symbol: {metadata.get('symbol','')}
    Type: {metadata.get('symbol_type','')}
    Language: {metadata.get('language','')}
    Lines: {metadata['start_line']}-{metadata['end_line']}

    {document}"""
        )

    context="\n\n---\n\n".join(context_parts)
    llm=GroqLLM()
    answer=llm.generate(query,context)

    print("\nRepoPilot:\n")
    print(answer)

    print("\nRelevant code:")
    for i,(document,metadata,score) in enumerate(ranked,start=1):
        symbol=metadata.get("symbol","")
        symbol_type=metadata.get("symbol_type","")
        print(f"\n{i}. {metadata['file_path']} (lines {metadata['start_line']}-{metadata['end_line']})")
        if symbol:
            print(f"   {symbol_type}: {symbol}")
        print(f"   relevance: {score:.3f}")
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