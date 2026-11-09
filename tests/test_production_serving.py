from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import api
from app.api import app
from app.auth import allowed_origins, require_csrf, require_same_origin


def test_health_and_spa_routes_remain_available():
    with TestClient(app) as client:
        health = client.get("/api/health")
        openapi = client.get("/openapi.json")
        docs = client.get("/docs")
        frontend = client.get("/chat/repository")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert openapi.status_code == 200
    assert docs.status_code == 200
    assert "Swagger UI" in docs.text
    assert frontend.status_code == 200
    assert '<div id="root"></div>' in frontend.text


def test_missing_assets_return_not_found_instead_of_spa():
    with TestClient(app) as client:
        response = client.get("/assets/does-not-exist.js")

    assert response.status_code == 404


def test_unknown_api_routes_remain_not_found():
    with TestClient(app) as client:
        response = client.get("/api/does-not-exist")

    assert response.status_code == 404


def test_production_origin_is_normalized_and_allowed(monkeypatch):
    monkeypatch.setenv("APP_ORIGIN", "https://RepoPilot.example.com/")
    assert "https://repopilot.example.com" in allowed_origins()

    request = SimpleNamespace(headers={"Origin": "https://REP OPILOT.example.com"})
    with pytest.raises(HTTPException):
        require_same_origin(request)

    accepted_request = SimpleNamespace(headers={"Origin": "https://REPOPILOT.example.com"})
    require_same_origin(accepted_request)


def test_untrusted_and_local_origins(monkeypatch):
    monkeypatch.setenv("APP_ORIGIN", "https://repopilot.example.com")

    local_request = SimpleNamespace(headers={"Origin": "http://localhost:5173"})
    require_same_origin(local_request)

    untrusted_request = SimpleNamespace(headers={"Origin": "https://evil.example.com"})
    with pytest.raises(HTTPException):
        require_same_origin(untrusted_request)


def test_csrf_protection_remains_required():
    request = SimpleNamespace(
        cookies={"repopilot_csrf": "cookie-token"},
        headers={"X-CSRF-Token": "different-token"},
    )
    with pytest.raises(HTTPException) as error:
        require_csrf(request)

    assert error.value.status_code == 403


def test_development_lifespan_allows_missing_frontend_build(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setattr(api, "FRONTEND_BUILD_AVAILABLE", False)
    monkeypatch.setattr(api, "Embedder", lambda: SimpleNamespace(load=lambda: None))
    monkeypatch.setattr(api, "Reranker", lambda: object())
    monkeypatch.setattr(api, "RepoPilotLLM", lambda: object())

    import asyncio

    async def start_application():
        async with api.lifespan(api.app):
            pass

    asyncio.run(start_application())


def test_production_lifespan_rejects_missing_frontend_build(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr(api, "FRONTEND_BUILD_AVAILABLE", False)

    import asyncio

    async def start_application():
        async with api.lifespan(api.app):
            pass

    with pytest.raises(RuntimeError, match="production frontend build is missing"):
        asyncio.run(start_application())
