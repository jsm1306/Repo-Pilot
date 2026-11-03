from types import SimpleNamespace

from app.vector_store import VectorStore


class FakeCollection:
    def __init__(self):
        self.upsert_call = None
        self.query_call = None

    def upsert(self, **kwargs):
        self.upsert_call = kwargs

    def query(self, **kwargs):
        self.query_call = kwargs
        return {"documents": [[]], "metadatas": [[]]}


class Embeddings:
    def tolist(self):
        return [[0.1, 0.2]]


def make_store():
    store = VectorStore.__new__(VectorStore)
    store.collection = FakeCollection()
    return store


def test_scoped_vectors_use_owner_repository_metadata_and_ids():
    store = make_store()
    chunk = SimpleNamespace(
        content="README content",
        file_path="README.md",
        start_line=1,
        end_line=1,
        language="markdown",
        symbol="Overview",
        symbol_type="heading",
    )

    store.add_chunks(
        [chunk],
        Embeddings(),
        "Guidewire_Hackathon",
        user_id="user-a",
        repository_id="repo-a",
    )

    call = store.collection.upsert_call
    assert call["ids"] == ["user-a:repo-a:README.md:1"]
    assert call["metadatas"][0]["user_id"] == "user-a"
    assert call["metadatas"][0]["repository_id"] == "repo-a"


def test_scoped_search_filters_both_owner_and_repository():
    store = make_store()

    store.search(
        query_embedding=SimpleNamespace(tolist=lambda: [0.1, 0.2]),
        repository_name="same-name",
        user_id="user-a",
        repository_id="repo-a",
    )

    assert store.collection.query_call["where"] == {
        "$and": [
            {"user_id": "user-a"},
            {"repository_id": "repo-a"},
        ]
    }


def test_identical_repository_names_have_distinct_scoped_ids():
    store = make_store()
    chunk = SimpleNamespace(
        content="same name, different owner",
        file_path="README.md",
        start_line=1,
        end_line=1,
        language="markdown",
        symbol="",
        symbol_type="document",
    )

    store.add_chunks([chunk], Embeddings(), "shared-name", user_id="user-a", repository_id="repo-a")
    first_id = store.collection.upsert_call["ids"][0]
    store.add_chunks([chunk], Embeddings(), "shared-name", user_id="user-b", repository_id="repo-b")
    second_id = store.collection.upsert_call["ids"][0]

    assert first_id != second_id
    assert first_id.startswith("user-a:repo-a:")
    assert second_id.startswith("user-b:repo-b:")


def test_legacy_search_remains_explicitly_name_scoped():
    store = make_store()

    store.search(
        query_embedding=SimpleNamespace(tolist=lambda: [0.1, 0.2]),
        repository_name="legacy-repository",
    )

    assert store.collection.query_call["where"] == {
        "$and": [
            {"repository": "legacy-repository"},
            {"storage_scope": "legacy"},
        ]
    }
