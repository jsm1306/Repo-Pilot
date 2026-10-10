from typing import List
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict

from app.embedder import Embedder
from app.vector_store import VectorStore
from app.reranker import Reranker


class RepoPilotRetriever(BaseRetriever):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    embedder: Embedder
    vector_store: VectorStore
    reranker: Reranker
    repository_name: str
    n_results: int = 10
    top_k: int = 5

    def _get_relevant_documents(self, query: str) -> List[Document]:
        query_embedding = self.embedder.embed([query])[0]

        results = self.vector_store.search(
            query_embedding,
            self.repository_name,
            n_results=self.n_results
        )

        documents = results["documents"][0]
        metadatas = results["metadatas"][0]

        if not documents:
            return []

        ranked = self.reranker.rerank(
            query,
            documents,
            metadatas,
            top_k=self.top_k
        )

        return [
            Document(
                page_content=document,
                metadata={
                    **metadata,
                    "reranker_score": score
                }
            )
            for document, metadata, score in ranked
        ]