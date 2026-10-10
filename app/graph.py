
from typing import TypedDict
from langgraph.graph import StateGraph, START, END


class RepoPilotState(TypedDict):
    question: str
    search_query: str
    context: str
    answer: str
    document_count: int
    relevance_grade: str
    retry_count: int


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
    MAX_RETRIES = 1

    def __init__(self, retriever, llm):
        self.retriever = retriever
        self.llm = llm

        builder = StateGraph(RepoPilotState)
        builder.add_node("retrieve", self.retrieve)
        builder.add_node("grade", self.grade_relevance)
        builder.add_node("rewrite", self.rewrite_question)
        builder.add_node("generate", self.generate)
        builder.add_node("fallback", self.fallback)

        builder.add_edge(START, "retrieve")
        builder.add_edge("retrieve", "grade")
        builder.add_conditional_edges(
            "grade",
            self.route_after_grading,
            {
                "generate": "generate",
                "rewrite": "rewrite",
                "fallback": "fallback"
            }
        )
        builder.add_edge("rewrite", "retrieve")
        builder.add_edge("generate", END)
        builder.add_edge("fallback", END)
        self.graph = builder.compile()

    def retrieve(self, state: RepoPilotState):
        query = state["search_query"]
        documents = self.retriever.invoke(query)
        context = format_documents(documents)

        print(f"\n[LangGraph] Search query: {query}")
        print(f"[LangGraph] Retrieved {len(documents)} chunks")

        for i, doc in enumerate(documents, start=1):
            print(
                f"\n--- Chunk {i} ---\n"
                f"File: {doc.metadata.get('file_path', '')}\n"
                f"Symbol: {doc.metadata.get('symbol', '')}\n"
                f"Lines: {doc.metadata.get('start_line', '')}-"
                f"{doc.metadata.get('end_line', '')}\n"
                f"{doc.page_content[:500]}"
            )

        return {"context": context, "document_count": len(documents)}

    def grade_relevance(self, state: RepoPilotState):
        if not state["context"].strip():
            print("\n[LangGraph] No evidence retrieved")
            return {"relevance_grade": "IRRELEVANT"}

        prompt = f"""
            You are a repository evidence relevance evaluator.

            Determine whether the retrieved context contains direct or meaningful
            evidence that can help answer the original question.

            Return RELEVANT if useful evidence exists.
            Return IRRELEVANT if the context is unrelated or contains no useful evidence.

            Do not answer the question. Evaluate only the evidence.

            Original question:
            {state["question"]}

            Retrieved context:
            {state["context"][:12000]}

            Return exactly one word: RELEVANT or IRRELEVANT.
            """
        response = self.llm.llm.invoke(prompt)
        result = response.content.strip().upper()
        grade = (
            "RELEVANT"
            if result.startswith("RELEVANT") and not result.startswith("IRRELEVANT")
            else "IRRELEVANT"
        )

        print(f"\n[LangGraph] LLM relevance grade: {grade}")
        return {"relevance_grade": grade}

    def route_after_grading(self, state: RepoPilotState):
        if state["relevance_grade"] == "RELEVANT":
            print("[LangGraph] Relevant evidence → Generate")
            return "generate"

        if state["retry_count"] < self.MAX_RETRIES:
            print("[LangGraph] Irrelevant evidence → Rewrite and retry")
            return "rewrite"

        print("[LangGraph] Retry exhausted → Fallback")
        return "fallback"

    def rewrite_question(self, state: RepoPilotState):
        prompt = f"""
            You are improving search queries for a code repository retrieval system.

            Rewrite the user's question into a concise query that is more likely to
            retrieve relevant source code, symbols, filenames, or documentation.

            Preserve the user's intent. Add useful technical terms only when justified.
            Do not answer the question. Return only the rewritten search query.

            Original question:
            {state["question"]}

            Previous search query:
            {state["search_query"]}
            """
        response = self.llm.llm.invoke(prompt)
        rewritten = response.content.strip().strip('"')

        if not rewritten:
            rewritten = state["question"]

        print(f"[LangGraph] Rewritten query: {rewritten}")
        return {
            "search_query": rewritten,
            "retry_count": state["retry_count"] + 1
        }

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
            "search_query": question,
            "context": "",
            "answer": "",
            "document_count": 0,
            "relevance_grade": "",
            "retry_count": 0
        })
        return result["answer"]
