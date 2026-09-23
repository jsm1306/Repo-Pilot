from sentence_transformers import CrossEncoder

class Reranker:
    def __init__(self,model_name="cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model=CrossEncoder(model_name)

    def rerank(self,query,documents,metadatas,top_k=5):
        candidates=[]

        for document,metadata in zip(documents,metadatas):
            context=f"""File: {metadata.get("file_path","")}
Symbol: {metadata.get("symbol","")}
Type: {metadata.get("symbol_type","")}
Language: {metadata.get("language","")}
Code:
{document}"""
            candidates.append(context)

        pairs=[(query,context) for context in candidates]
        scores=self.model.predict(pairs)

        ranked=sorted(
            zip(documents,metadatas,scores),
            key=lambda item:item[2],
            reverse=True
        )

        return ranked[:top_k]