"""Application startup, CORS, and health endpoint tests."""

from fastapi.testclient import TestClient

from app.main import app, build_frontend_origins


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_frontend_origins_include_configured_production_origin() -> None:
    origins = build_frontend_origins("https://wander.example.com/, https://demo.example.com")

    assert "http://localhost:3000" in origins
    assert "http://127.0.0.1:3000" in origins
    assert "https://wander.example.com" in origins
    assert "https://demo.example.com" in origins
    assert "*" not in origins
