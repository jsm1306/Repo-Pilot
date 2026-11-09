
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.db_models import RepositoryChunk


class VectorStore:
    """PostgreSQL + pgvector-backed repository vector storage."""

    def __init__(self, session: Session | None = None):
        self.session = session

    def add_chunks(self,chunks,embeddings,repository_name,user_id=None,repository_id=None,):
        if user_id is None or repository_id is None:
            raise ValueError(
                "user_id and repository_id are required for scoped storage."
            )

        if len(chunks) != len(embeddings):
            raise ValueError("Chunks and embeddings must have the same length.")

        if not chunks:
            return

        embedding_rows = (
            embeddings.tolist()
            if hasattr(embeddings, "tolist")
            else list(embeddings)
        )

        if any(len(vector) != 384 for vector in embedding_rows):
            raise ValueError("Every embedding must contain exactly 384 dimensions.")

        rows = [
            RepositoryChunk(
                user_id=user_id,
                repository_id=repository_id,
                content=chunk.content,
                embedding=vector,
                file_path=chunk.file_path,
                language=chunk.language,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                symbol=chunk.symbol or None,
                symbol_type=chunk.symbol_type or None,
            )
            for chunk, vector in zip(chunks, embedding_rows)
        ]

        # Delete and insert in one transaction so a failed re-index
        # does not leave the repository with an incomplete index.
        with SessionLocal.begin() as session:
            session.execute(
                delete(RepositoryChunk).where(
                    RepositoryChunk.user_id == user_id,
                    RepositoryChunk.repository_id == repository_id,
                )
            )
            session.add_all(rows)

    def search(
        self,
        query_embedding,
        repository_name=None,
        n_results=5,
        user_id=None,
        repository_id=None,
    ):
        if user_id is None or repository_id is None:
            raise ValueError(
                "user_id and repository_id are required for scoped search."
            )

        query_vector = (
            query_embedding.tolist()
            if hasattr(query_embedding, "tolist")
            else list(query_embedding)
        )

        if len(query_vector) != 384:
            raise ValueError("Query embedding must contain exactly 384 dimensions.")

        statement = (
            select(
                RepositoryChunk.content,
                RepositoryChunk.file_path,
                RepositoryChunk.language,
                RepositoryChunk.start_line,
                RepositoryChunk.end_line,
                RepositoryChunk.symbol,
                RepositoryChunk.symbol_type,
                RepositoryChunk.user_id,
                RepositoryChunk.repository_id,
                RepositoryChunk.embedding.cosine_distance(query_vector).label(
                    "distance"
                ),
            )
            .where(
                RepositoryChunk.user_id == user_id,
                RepositoryChunk.repository_id == repository_id,
            )
            .order_by("distance")
            .limit(n_results)
        )

        if getattr(self, "session", None) is None:
            with SessionLocal() as session:
                results = session.execute(statement).all()
        else:
            results = self.session.execute(statement).all()

        documents = []
        metadatas = []
        distances = []

        for row in results:
            documents.append(row.content)
            metadatas.append(
                {
                    "repository": repository_name or "",
                    "storage_scope": "scoped",
                    "file_path": row.file_path,
                    "language": row.language,
                    "start_line": row.start_line,
                    "end_line": row.end_line,
                    "symbol": row.symbol or "",
                    "symbol_type": row.symbol_type or "",
                    "user_id": str(row.user_id),
                    "repository_id": str(row.repository_id),
                }
            )
            distances.append(float(row.distance))

        # Preserve the result shape expected by the existing
        # LangChain retriever and repository search tools.
        return {
            "documents": [documents],
            "metadatas": [metadatas],
            "distances": [distances],
        }

    def get_repositories(self):
        """Return distinct repository IDs and names from indexed chunks."""
        with SessionLocal() as session:
            rows = session.execute(
                select(
                    RepositoryChunk.repository_id,
                    RepositoryChunk.user_id,
                ).distinct()
            ).all()

        return rows
