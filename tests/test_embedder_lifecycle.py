
import sys
from types import SimpleNamespace

import numpy as np

from app.embedder import Embedder


def test_embedder_loads_model_only_once(monkeypatch):
    calls = []

    class FakeSentenceTransformer:
        def __init__(self, model_name):
            calls.append(model_name)

        def encode(self, texts, convert_to_numpy=True):
            return np.zeros((len(texts), 384))

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
    )

    embedder = Embedder()

    assert embedder.model is None

    embedder.load()
    first_model = embedder.model

    embedder.load()

    assert embedder.model is first_model
    assert calls == ["all-MiniLM-L6-v2"]


def test_embedder_embed_preserves_lazy_loading(monkeypatch):
    calls = []

    class FakeSentenceTransformer:
        def __init__(self, model_name):
            calls.append(model_name)

        def encode(self, texts, convert_to_numpy=True):
            return np.zeros((len(texts), 384))

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
    )

    embedder = Embedder()

    # Constructor should not load the model.
    assert calls == []

    result = embedder.embed(["Docker configuration"])

    assert result.shape == (1, 384)
    assert calls == ["all-MiniLM-L6-v2"]

    # Subsequent calls reuse the model.
    embedder.embed(["Jenkins pipeline"])

    assert calls == ["all-MiniLM-L6-v2"]
