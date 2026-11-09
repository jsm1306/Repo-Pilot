from types import SimpleNamespace

import pytest

from app.graph import RepoPilotGraph, is_insufficient_evidence


class FakeRetriever:
    def __init__(self, documents):
        self.documents = documents
        self.queries = []

    def invoke(self, query):
        self.queries.append(query)
        return self.documents


class FakeResponse:
    def __init__(self, content):
        self.content = content


class FakeLLM:
    def __init__(self, content):
        self.content = content
        self.calls = []
        self.llm = self

    def invoke(self, prompt):
        self.calls.append(prompt)
        return FakeResponse(self.content)


def make_document():
    return SimpleNamespace(
        page_content="Docker packages the service into a container.",
        metadata={
            "file_path": "Dockerfile",
            "symbol": "",
            "symbol_type": "dockerfile",
            "language": "dockerfile",
            "start_line": 1,
            "end_line": 3,
            "reranker_score": 0.9,
        },
    )


def test_graph_answers_with_one_llm_call_and_preserves_evidence():
    retriever = FakeRetriever([make_document()])
    llm = FakeLLM("Docker packages the service into a container.")
    graph = RepoPilotGraph(retriever, llm)
    events = []

    result = graph.run_with_state("What is Docker used for?", event_callback=events.append)

    assert len(llm.calls) == 1
    assert result["answer"] == "Docker packages the service into a container."
    assert result["relevance_grade"] == "RELEVANT"
    assert result["retry_count"] == 0
    assert result["document_count"] == 1
    assert result["evidence"][0]["file_path"] == "Dockerfile"
    assert any(
        event["stage"] == "evidence_graded" and event["status"] == "completed"
        for event in events
    )


def test_graph_falls_back_without_calling_llm_when_no_evidence_exists():
    retriever = FakeRetriever([])
    llm = FakeLLM("should not be used")
    graph = RepoPilotGraph(retriever, llm)

    result = graph.run_with_state("What is Docker used for?")

    assert llm.calls == []
    assert result["relevance_grade"] == "IRRELEVANT"
    assert result["retry_count"] == 0
    assert result["answer"].startswith("I couldn't find relevant repository context")


def test_graph_falls_back_when_llm_marks_context_insufficient():
    retriever = FakeRetriever([make_document()])
    llm = FakeLLM("INSUFFICIENT_EVIDENCE")
    graph = RepoPilotGraph(retriever, llm)

    result = graph.run_with_state("What is the deployment region?")

    assert len(llm.calls) == 1
    assert result["relevance_grade"] == "IRRELEVANT"
    assert result["answer"].startswith("I couldn't find relevant repository context")


@pytest.mark.parametrize(
    "answer",
    [
        "INSUFFICIENT_EVIDENCE",
        " insufficient_evidence ",
        "Insufficient_Evidence.",
        "INSUFFICIENT_EVIDENCE!!!",
    ],
)
def test_insufficient_evidence_detection_normalizes_model_output(answer):
    assert is_insufficient_evidence(answer)


def test_graph_does_not_treat_longer_answer_as_insufficient_evidence():
    assert not is_insufficient_evidence(
        "INSUFFICIENT_EVIDENCE because the context is incomplete."
    )


class RepositoryFunctionRetriever(FakeRetriever):
    def __init__(self):
        super().__init__([])
        self.document = make_document()

    def invoke(self, query):
        self.queries.append(query)
        return [self.document] if query else []


@pytest.mark.parametrize(
    "question",
    [
        "How is Docker used in this repository?",
        "What packages the service into a container?",
        "Where is the containerized deployment configured?",
    ],
)
def test_direct_retrieval_handles_differently_worded_questions(question):
    retriever = RepositoryFunctionRetriever()
    llm = FakeLLM("Docker packages the service into a container.")
    graph = RepoPilotGraph(retriever, llm)

    result = graph.run_with_state(question)

    assert retriever.queries == [question]
    assert result["relevance_grade"] == "RELEVANT"
    assert result["evidence"][0]["file_path"] == "Dockerfile"
    assert "Docker" in result["answer"]


def test_direct_retrieval_preserves_legacy_rewrite_retrieval_coverage():
    questions = [
        "How is Docker used in this repository?",
        "What packages the service into a container?",
        "Where is the containerized deployment configured?",
    ]
    legacy_rewrites = {
        question: "Docker containerization"
        for question in questions
    }

    direct_retriever = RepositoryFunctionRetriever()
    direct_graph = RepoPilotGraph(
        direct_retriever,
        FakeLLM("Docker packages the service into a container."),
    )
    direct_results = [
        direct_graph.run_with_state(question)
        for question in questions
    ]

    legacy_retriever = RepositoryFunctionRetriever()
    legacy_graph = RepoPilotGraph(
        legacy_retriever,
        FakeLLM("Docker packages the service into a container."),
    )
    legacy_results = [
        legacy_graph.run_with_state(legacy_rewrites[question])
        for question in questions
    ]

    assert all(result["relevance_grade"] == "RELEVANT" for result in direct_results)
    assert all(result["relevance_grade"] == "RELEVANT" for result in legacy_results)
    assert [result["evidence"] for result in direct_results] == [
        result["evidence"] for result in legacy_results
    ]
    assert direct_retriever.queries == questions
    assert legacy_retriever.queries == [legacy_rewrites[question] for question in questions]
