
from typing import TypedDict
from langgraph.graph import StateGraph, START, END


class RepoPilotState(TypedDict):
    question: str
    context: str
    answer: str
    document_count: int
    relevance_grade: str


def format_documents(documents):
    return "\n\n---\n\n".join(
        f"""File: {doc.metadata.get('file_path', '')}
Symbol: {doc.metadata.get('symbol', '')}
Type: {doc.metadata.get('symbol_type', '')}
Language: {doc.metadata.get('language', '')}
Lines: {doc.metadata.get('start_line', '')}-{doc.metadata.get('end_line', '')}
{doc.page_content}"""
        for doc in documents
    )


class RepoPilotGraph:
    
    def __init__(self, retriever, llm):
        self.retriever = retriever
        self.llm = llm

        builder = StateGraph(RepoPilotState)
        builder.add_node("retrieve", self.retrieve)
        builder.add_node("grade", self.grade_relevance)
        builder.add_node("generate", self.generate)
        builder.add_node("fallback", self.fallback)

        builder.add_edge(START, "retrieve")
        builder.add_edge("retrieve", "grade")

        builder.add_conditional_edges(
            "grade",
            self.route_after_grading,
            {
                "generate": "generate",
                "fallback": "fallback"
            }
        )

        builder.add_edge("generate", END)
        builder.add_edge("fallback", END)

        self.graph = builder.compile()

    def retrieve(self, state: RepoPilotState):
        documents = self.retriever.invoke(state["question"])
        context = format_documents(documents)

        print(f"\n[LangGraph] Retrieved {len(documents)} chunks:")
        for i, doc in enumerate(documents, start=1):
            print(
                f"\n--- Chunk {i} ---\n"
                f"File: {doc.metadata.get('file_path', '')}\n"
                f"Symbol: {doc.metadata.get('symbol', '')}\n"
                f"Lines: {doc.metadata.get('start_line', '')}-"
                f"{doc.metadata.get('end_line', '')}\n"
                f"{doc.page_content[:500]}"
            )

        return {
            "context": context,
            "document_count": len(documents),
            "relevance_scores": [
                float(doc.metadata["reranker_score"])
                for doc in documents
                if "reranker_score" in doc.metadata
            ]
        }

    
    
    def route_after_retrieval(self, state: RepoPilotState):
        scores = state.get("relevance_scores", [])
        print(f"\n[LangGraph] Relevance scores: {scores}")

        if scores and max(scores) >= state.get("relevance_threshold", 0.0):
            print("[LangGraph] Relevant evidence → Generate")
            return "generate"

        print("[LangGraph] Insufficient evidence → Fallback")
        return "fallback"

    
    def grade_relevance(self, state: RepoPilotState):
        prompt = f"""
            You are a repository evidence relevance evaluator.

            Determine whether the retrieved context contains information
            that can help answer the user's question.

            Return RELEVANT if the context contains direct or meaningful
            evidence that helps answer the question.

            Return IRRELEVANT if the context is unrelated, merely shares
            incidental keywords, or does not contain useful evidence.

            Do not answer the user's question. Evaluate only the evidence.

            Question:
            {state["question"]}

            Retrieved context:
            {state["context"][:12000]}

            Return exactly one word: RELEVANT or IRRELEVANT.
            """

        response = self.llm.llm.invoke(prompt)
        result = response.content.strip().upper()
        grade = "RELEVANT" if result.startswith("RELEVANT") and not result.startswith("IRRELEVANT") else "IRRELEVANT"

        print(f"\n[LangGraph] LLM relevance grade: {grade}")
        return {"relevance_grade": grade}


    def route_after_grading(self, state: RepoPilotState):
        if state["relevance_grade"] == "RELEVANT":
            print("[LangGraph] Relevant evidence → Generate")
            return "generate"

        print("[LangGraph] Irrelevant evidence → Fallback")
        return "fallback"


    def generate(self, state: RepoPilotState):
        response = self.llm.chain.invoke({
            "question": state["question"],
            "context": state["context"]
        })
        return {"answer": response}

    def fallback(self, state: RepoPilotState):
        return {
            "answer": (
                "I couldn't find relevant repository context to answer "
                "this question reliably. Try rephrasing it or indexing "
                "the relevant files first."
            )
        }

    def run(self, question: str):
        result = self.graph.invoke({
            "question": question,
            "context": "",
            "answer": "",
            "document_count": 0,
            "relevance_grade": ""
        })
        return result["answer"]
