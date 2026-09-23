import chromadb

class VectorStore:
    def __init__(self, persist_directory="chroma_db"):
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection("repository_code")

    def add_chunks(self,chunks,embeddings,repository_name):
        documents=[chunk.content for chunk in chunks]
        ids=[f"{repository_name}:{chunk.file_path}:{chunk.start_line}" for chunk in chunks]
        metadatas=[{"repository":repository_name,"file_path":chunk.file_path,"language":chunk.language,"start_line":chunk.start_line,"end_line":chunk.end_line,"symbol":chunk.symbol or "","symbol_type":chunk.symbol_type or ""} for chunk in chunks]
        self.collection.upsert(ids=ids,documents=documents,embeddings=embeddings.tolist(),metadatas=metadatas)

    def search(self, query_embedding, repository_name,n_results=5):
        return self.collection.query(query_embeddings=[query_embedding.tolist()],n_results=n_results,where={"repository":repository_name})

    def get_repositories(self):
        results=self.collection.get(include=["metadatas"])
        repositories=set()
        for metadata in results["metadatas"]:
            if metadata and "repository" in metadata:
                repositories.add(metadata["repository"])
        return sorted(repositories)