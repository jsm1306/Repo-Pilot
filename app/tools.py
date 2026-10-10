from pathlib import Path
from langchain_core.tools import tool
from app.embedder import Embedder
from app.vector_store import VectorStore
from app.reranker import Reranker
from dotenv import load_dotenv

load_dotenv()

@tool
def search_repository(query: str, repository_name: str) -> str:
    """Search the indexed repository for code relevant to the query."""

    embedder = Embedder()
    vector_store = VectorStore()
    reranker = Reranker()

    query_embedding = embedder.embed([query])[0]

    results = vector_store.search(
        query_embedding,
        repository_name,
        n_results=10
    )

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]

    if not documents:
        return "No relevant code was found."

    ranked = reranker.rerank(
        query,
        documents,
        metadatas,
        top_k=5
    )

    output = []

    for document, metadata, score in ranked:
        output.append(
            f"""File: {metadata.get('file_path', '')}
Symbol: {metadata.get('symbol', '')}
Type: {metadata.get('symbol_type', '')}
Language: {metadata.get('language', '')}
Lines: {metadata.get('start_line', '')}-{metadata.get('end_line', '')}
Relevance: {score:.3f}

{document}"""
        )

    return "\n\n---\n\n".join(output)


@tool
def read_repository_file(file_path: str, repository_path: str) -> str:
    """Read the complete contents of a file from the repository."""

    path = Path(repository_path) / file_path

    if not path.exists():
        return f"File not found: {file_path}"

    if not path.is_file():
        return f"Path is not a file: {file_path}"

    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"Unable to read file as UTF-8: {file_path}"