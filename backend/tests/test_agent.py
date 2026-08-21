"""Exploration agent tests."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.explore import ExploreRequest
from app.models.feedback import FeedbackRecord, FeedbackValue
from app.models.memory import MemoryProfile
from app.services.exploration_agent import run_exploration
from app.services.memory_service import refresh_memory

client = TestClient(app)


def _build_feedback(anonymous_user_id: str = "agent-user") -> FeedbackRecord:
    return FeedbackRecord(
        id=1,
        anonymous_user_id=anonymous_user_id,
        target_type="knowledge_node",
        target_id="1",
        target_label="建筑空间设计",
        target_domain="建筑学",
        root_topic="游戏开发",
        value="like",
        surprise_level=0.5,
        generation_source="llm",
        created_at="2024-01-01T00:00:00+00:00",
        updated_at="2024-01-01T00:00:00+00:00",
    )


def test_run_exploration_without_memory_returns_baseline(tmp_path, monkeypatch):
    db_path = str(tmp_path / "feedback.db")
    monkeypatch.setenv("FEEDBACK_DB_PATH", db_path)

    with patch("app.services.exploration_agent.get_llm_service", return_value=None):
        response, metrics = run_exploration(
            ExploreRequest(topic="游戏开发", surprise_level=0.5, anonymous_user_id=None, use_memory=False)
        )

    assert len(response.nodes) == 6
    assert response.generation_source == "fallback"
    assert metrics is not None
    assert metrics.memory_retrieval_ms == 0.0


def test_run_exploration_with_memory_returns_metadata(tmp_path, monkeypatch):
    db_path = str(tmp_path / "feedback.db")
    monkeypatch.setenv("FEEDBACK_DB_PATH", db_path)
    from app.services.memory_service import init_memory_db
    init_memory_db(db_path)

    client.put("/api/feedback", json={
        "anonymous_user_id": "agent-user",
        "target_type": "knowledge_node",
        "target_id": "1",
        "target_label": "建筑空间设计",
        "target_domain": "建筑学",
        "root_topic": "游戏开发",
        "value": "like",
        "surprise_level": 0.5,
        "generation_source": "llm",
    })

    with patch("app.services.exploration_agent.get_llm_service", return_value=None):
        response, metrics = run_exploration(
            ExploreRequest(topic="游戏开发", surprise_level=0.5, anonymous_user_id="agent-user", use_memory=True)
        )

    assert len(response.nodes) == 6
    assert metrics is not None
    assert metrics.memory_retrieval_ms > 0
    assert metrics.exploration_ratio >= 0.0


def test_explore_api_accepts_memory_fields(tmp_path, monkeypatch):
    db_path = str(tmp_path / "feedback.db")
    monkeypatch.setenv("FEEDBACK_DB_PATH", db_path)
    from app.services.memory_service import init_memory_db
    init_memory_db(db_path)

    with patch("app.services.explore_service.get_llm_service", return_value=None):
        response = client.post(
            "/api/explore",
            json={
                "topic": "游戏开发",
                "surprise_level": 0.5,
                "anonymous_user_id": "api-user",
                "use_memory": True,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert "metadata" in payload
    assert payload["metadata"]["memory"] is not None
    assert payload["metadata"]["agent_metrics"] is not None


def test_explore_api_ignores_memory_when_disabled(tmp_path, monkeypatch):
    db_path = str(tmp_path / "feedback.db")
    monkeypatch.setenv("FEEDBACK_DB_PATH", db_path)
    from app.services.memory_service import init_memory_db
    init_memory_db(db_path)

    with patch("app.services.explore_service.get_llm_service", return_value=None):
        response = client.post(
            "/api/explore",
            json={
                "topic": "游戏开发",
                "surprise_level": 0.5,
                "anonymous_user_id": "api-user",
                "use_memory": False,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert "metadata" in payload
    assert payload["metadata"]["memory"] is None
    assert payload["metadata"]["agent_metrics"] is None
