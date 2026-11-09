class Embedder:
    def __init__(self,model_name="all-MiniLM-L6-v2"):
        self.model_name=model_name
        self.model=None

    def load(self):
        """Load the embedding model if it has not been loaded already."""
        if self.model is None:
            from sentence_transformers import SentenceTransformer
            self.model=SentenceTransformer(self.model_name)

    def embed(self, texts):
        self.load()
        return self.model.encode(texts,convert_to_numpy=True)