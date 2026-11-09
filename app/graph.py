
from collections.abc import Callable
import string
from typing import Any, TypedDict
from langgraph.graph import StateGraph, START, END


class RepoPilotState(TypedDict):
    question: str
    context: str
    answer: str
    document_count: int
    relevance_grade: str
    retry_count: int
    evidence: list[dict[str, Any]]


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


def is_insufficient_evidence(answer: str) -> bool:
    normalized = answer.strip().rstrip(string.punctuation).strip().casefold()
    return normalized == "insufficient_evidence"


class RepoPilotGraph:
    def __init__(self, retriever, llm):
        self.retriever = retriever
        self.llm = llm
        self._event_callback: Callable[[dict[str, Any]], None] | None = None

        builder = StateGraph(RepoPilotState)
        builder.add_node("retrieve", self.retrieve)
        builder.add_node("answer", self.answer)

        builder.add_edge(START, "retrieve")
        builder.add_edge("retrieve", "answer")
        builder.add_edge("answer", END)
        self.graph = builder.compile()

    def _emit(self, event_type: str, **data: Any) -> None:
        if self._event_callback:
            self._event_callback({"type": event_type, **data})

    def retrieve(self, state: RepoPilotState):
        query = state["question"]
        self._emit("stage", stage="context_retrieved", status="running", message="Retrieving repository context.")
        documents = self.retriever.invoke(query)
        context = format_documents(documents)

        evidence = [
            {
                "file_path": doc.metadata.get("file_path", ""),
                "symbol": doc.metadata.get("symbol", ""),
                "symbol_type": doc.metadata.get("symbol_type", ""),
                "language": doc.metadata.get("language", ""),
                "start_line": doc.metadata.get("start_line"),
                "end_line": doc.metadata.get("end_line"),
                "content": doc.page_content,
                "reranker_score": (
                    float(doc.metadata["reranker_score"])
                    if doc.metadata.get("reranker_score") is not None
                    else None
                ),
            }
            for doc in documents
        ]

        result = {
            "context": context,
            "document_count": len(documents),
            "evidence": evidence,
        }
        self._emit(
            "stage",
            stage="context_retrieved",
            status="completed",
            message=f"{len(documents)} source chunks retrieved.",
            document_count=len(documents),
            evidence=evidence,
        )
        return result

    def answer(self, state: RepoPilotState):
        self._emit("stage", stage="evidence_graded", status="running", message="Evaluating retrieved evidence.")
        if not state["context"].strip():
            result = {
                **self.fallback(state),
                "relevance_grade": "IRRELEVANT",
            }
            self._emit(
                "stage",
                stage="evidence_graded",
                status="completed",
                message="No evidence was available to grade.",
                relevance_grade="IRRELEVANT",
            )
            return result

        self._emit("stage", stage="answer_generated", status="running", message="Generating the answer from repository context.")
        prompt = f"""
You are RepoPilot, an AI repository analysis assistant.

Answer the user's question using only the repository context below.
If the context does not contain useful evidence for the question, respond with
exactly INSUFFICIENT_EVIDENCE and nothing else.
Never invent repository details or rely on information outside the context.
Otherwise, answer directly and mention relevant file paths and symbols when possible.
Do not include a prefix such as "Answer:".

Repository context:
{state["context"][:12000]}

User question:
{state["question"]}
"""
        response = self.llm.llm.invoke(prompt)
        answer = response.content.strip()

        if is_insufficient_evidence(answer) or not answer:
            result = self.fallback(state)
            result["relevance_grade"] = "IRRELEVANT"
            self._emit(
                "stage",
                stage="evidence_graded",
                status="completed",
                message="Evidence was insufficient to answer the question.",
                relevance_grade="IRRELEVANT",
            )
            self._emit(
                "stage",
                stage="answer_generated",
                status="completed",
                message="Fallback answer generated.",
            )
            return result

        self._emit(
            "stage",
            stage="evidence_graded",
            status="completed",
            message="Evidence was sufficient to answer the question.",
            relevance_grade="RELEVANT",
        )
        self._emit("stage", stage="answer_generated", status="completed", message="Answer generated.")
        return {
            "answer": answer,
            "relevance_grade": "RELEVANT",
        }

    def fallback(self, state: RepoPilotState):
        answer = (
            "I couldn't find relevant repository context to answer "
            "this question reliably. Try rephrasing it or indexing "
            "the relevant files first."
        )
        self._emit("stage", stage="answer_generated", status="completed", message="Fallback answer generated.")
        return {
            "answer": answer
        }

    def run(self, question: str):
        return self.run_with_state(question)["answer"]

    def run_with_state(
        self,
        question: str,
        event_callback: Callable[[dict[str, Any]], None] | None = None,
    ):
        self._event_callback = event_callback
        self._emit("stage", stage="question_received", status="completed", message="Question received.")
        result = self.graph.invoke({
            "question": question,
            "context": "",
            "answer": "",
            "document_count": 0,
            "relevance_grade": "",
            "retry_count": 0,
            "evidence": []
        })
        self._event_callback = None
        return result
