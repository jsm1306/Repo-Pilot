import chromadb

class VectorStore:
    def __init__(self, persist_directory="chroma_db"):
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection("repository_code")

    def add_chunks(self, chunks, embeddings, repository_name, user_id=None, repository_id=None):
        if (user_id is None) != (repository_id is None):
            raise ValueError("Both user_id and repository_id are required for scoped storage.")
        documents=[chunk.content for chunk in chunks]
        namespace = f"{user_id}:{repository_id}" if user_id is not None else f"legacy:{repository_name}"
        ids=[f"{namespace}:{chunk.file_path}:{chunk.start_line}" for chunk in chunks]
        metadatas=[{
            "repository": repository_name,
            "storage_scope": "scoped" if user_id is not None else "legacy",
            "file_path": chunk.file_path,
            "language": chunk.language,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "symbol": chunk.symbol or "",
            "symbol_type": chunk.symbol_type or "",
            **({"user_id": str(user_id), "repository_id": str(repository_id)} if user_id is not None else {}),
        } for chunk in chunks]
        self.collection.upsert(ids=ids,documents=documents,embeddings=embeddings.tolist(),metadatas=metadatas)

    def search(self, query_embedding, repository_name=None, n_results=5, user_id=None, repository_id=None):
        if user_id is not None or repository_id is not None:
            if user_id is None or repository_id is None:
                raise ValueError("Both user_id and repository_id are required for scoped search.")
            where = {
                "$and": [
                    {"user_id": str(user_id)},
                    {"repository_id": str(repository_id)},
                ]
            }
        elif repository_name is not None:
            where = {
                "$and": [
                    {"repository": repository_name},
                    {"storage_scope": "legacy"},
                ]
            }
        else:
            raise ValueError("A repository scope is required.")
        return self.collection.query(query_embeddings=[query_embedding.tolist()],n_results=n_results,where=where)

    def get_repositories(self):
        results=self.collection.get(include=["metadatas"])
        repositories=set()
        for metadata in results["metadatas"]:
            if metadata and "repository" in metadata:
                repositories.add(metadata["repository"])
        return sorted(repositories)