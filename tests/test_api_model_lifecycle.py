import asyncio
import uuid
from types import SimpleNamespace

from app import api
from app import reranker as reranker_module
from types import SimpleNamespace

def test_lifespan_initializes_models_once(monkeypatch):
    instances = {}
    counts = {"embedder": 0, "reranker": 0, "llm": 0}
    load_counts = {"embedder": 0}

    class FakeEmbedder:
        def load(self):
            load_counts["embedder"] += 1

    for name in counts:
        def make_factory(resource_name):
            def factory():
                counts[resource_name] += 1

                instance = (
                    FakeEmbedder()
                    if resource_name == "embedder"
                    else object()
                )

                instances[resource_name] = instance
                return instance

            return factory

        factory_name = {
            "embedder": "Embedder",
            "reranker": "Reranker",
            "llm": "RepoPilotLLM",
        }[name]

        monkeypatch.setattr(
            api,
            factory_name,
            make_factory(name),
        )

    async def exercise():
        async with api.lifespan(api.app):
            assert api.app.state.embedder is instances["embedder"]
            assert api.app.state.reranker is instances["reranker"]
            assert api.app.state.llm is instances["llm"]

    asyncio.run(exercise())

    assert counts == {
        "embedder": 1,
        "reranker": 1,
        "llm": 1,
    }

    assert load_counts["embedder"] == 1

def test_sync_endpoint_uses_shared_models(monkeypatch):
    user_id = uuid.uuid4()

    shared = {
        "embedder": object(),
        "reranker": object(),
        "llm": object(),
    }

    app_state = SimpleNamespace(**shared)
    request = SimpleNamespace(
        app=SimpleNamespace(state=app_state)
    )

    captured = {}

    def fake_run_question(question_request, current_user_id, db, **kwargs):
        captured["models"] = kwargs
        captured["user_id"] = current_user_id
        return {
            "answer": "Docker is used for containerization.",
            "document_count": 1,
            "relevance_grade": "RELEVANT",
            "retry_count": 0,
            "evidence": [],
        }

    monkeypatch.setattr(api, "require_csrf", lambda _request: None)
    monkeypatch.setattr(api, "_run_question", fake_run_question)

    response = api.ask_question(
        request=api.QuestionRequest(
            repository_name="repo-one",
            question="What is Docker used for?",
        ),
        http_request=request,
        current_user=SimpleNamespace(id=user_id),
        db=object(),
    )

    assert response.answer == "Docker is used for containerization."
    assert captured["user_id"] == user_id

    assert captured["models"]["embedder"] is shared["embedder"]
    assert captured["models"]["reranker"] is shared["reranker"]
    assert captured["models"]["llm"] is shared["llm"]


def test_stream_endpoint_uses_shared_models(monkeypatch):
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()

    shared = {
        "embedder": object(),
        "reranker": object(),
        "llm": object(),
    }

    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(**shared)
        )
    )

    chat_session = SimpleNamespace(
        id=session_id,
        repository=SimpleNamespace(name="repo-one"),
    )

    class FakeDatabase:
        def scalar(self, _statement):
            return chat_session

        def add(self, _item):
            pass

        def commit(self):
            pass

    class FakeWorkerDatabase:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def add(self, _item):
            pass

        def commit(self):
            pass

    class ImmediateThread:
        def __init__(self, target, daemon=None):
            self.target = target

        def start(self):
            self.target()

    captured = {}

    def fake_run_question(
        question_request,
        current_user_id,
        db,
        **kwargs,
    ):
        captured["models"] = kwargs
        captured["user_id"] = current_user_id

        return {
            "answer": "Docker packages applications into containers.",
            "document_count": 1,
            "relevance_grade": "RELEVANT",
            "retry_count": 0,
            "evidence": [],
        }

    monkeypatch.setattr(api, "SessionLocal", FakeWorkerDatabase)
    monkeypatch.setattr(api.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(api, "_run_question", fake_run_question)

    response = api.stream_question(
        repository_name="repo-one",
        question="What is Docker?",
        session_id=str(session_id),
        http_request=request,
        current_user=SimpleNamespace(id=user_id),
        db=FakeDatabase(),
    )

    assert isinstance(response, api.StreamingResponse)
    assert captured["user_id"] == user_id

    assert captured["models"]["embedder"] is shared["embedder"]
    assert captured["models"]["reranker"] is shared["reranker"]
    assert captured["models"]["llm"] is shared["llm"]

def test_question_graphs_reuse_models_but_keep_request_scope(monkeypatch):
    shared = {
        "embedder": object(),
        "reranker": object(),
        "llm": object(),
    }
    repository_ids = [uuid.uuid4(), uuid.uuid4()]
    user_ids = [uuid.uuid4(), uuid.uuid4()]
    retrievers = []
    graphs = []

    class FakeRetriever:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            retrievers.append(self)

    class FakeGraph:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            graphs.append(self)

    class FakeDatabase:
        def __init__(self, repository_id):
            self.repository_id = repository_id

        def scalar(self, _statement):
            return SimpleNamespace(id=self.repository_id)

    monkeypatch.setattr(api, "VectorStore", lambda _session: object())
    monkeypatch.setattr(api, "RepoPilotRetriever", FakeRetriever)
    monkeypatch.setattr(api, "RepoPilotGraph", FakeGraph)

    first = api._build_question_graph(
        "repo-one",
        user_ids[0],
        FakeDatabase(repository_ids[0]),
        **shared,
    )

    second = api._build_question_graph(
        "repo-two",
        user_ids[1],
        FakeDatabase(repository_ids[1]),
        **shared,
    )

    assert first is not second
    assert graphs[0].kwargs["llm"] is shared["llm"]
    assert graphs[1].kwargs["llm"] is shared["llm"]
    assert retrievers[0].kwargs["embedder"] is shared["embedder"]
    assert retrievers[1].kwargs["reranker"] is shared["reranker"]
    assert retrievers[0].kwargs["repository_name"] == "repo-one"
    assert retrievers[1].kwargs["repository_name"] == "repo-two"
    assert retrievers[0].kwargs["user_id"] == str(user_ids[0])
    assert retrievers[1].kwargs["user_id"] == str(user_ids[1])
    assert retrievers[0].kwargs["repository_id"] == str(repository_ids[0])
    assert retrievers[1].kwargs["repository_id"] == str(repository_ids[1])


def test_reranker_uses_configured_batch_size(monkeypatch):
    calls = []

    class FakeCrossEncoder:
        def predict(self, pairs, batch_size):
            calls.append((pairs, batch_size))
            return [0.5]

    monkeypatch.setattr(reranker_module, "CrossEncoder", lambda _model_name: FakeCrossEncoder())

    reranker = reranker_module.Reranker(batch_size=4)
    reranker.rerank("question", ["document"], [{}], top_k=1)

    assert calls[0][1] == 4
