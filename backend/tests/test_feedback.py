"""Feedback API tests."""

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _build_request(
    target_type: str = "knowledge_node",
    target_id: str = "candidate-1",
    target_label: str = "视觉文化",
    target_domain: str = "文化研究",
    root_topic: str = "摄影史",
    value: str = "like",
    anonymous_user_id: str = "user-a",
    surprise_level: float = 0.5,
    generation_source: str | None = "llm",
) -> dict:
    return {
        "anonymous_user_id": anonymous_user_id,
        "target_type": target_type,
        "target_id": target_id,
        "target_label": target_label,
        "target_domain": target_domain,
        "root_topic": root_topic,
        "value": value,
        "surprise_level": surprise_level,
        "generation_source": generation_source,
    }


def test_db_initializes_on_first_request(tmp_path, monkeypatch):
    db_path = str(tmp_path / "feedback.db")
    monkeypatch.setenv("FEEDBACK_DB_PATH", db_path)

    response = client.put("/api/feedback", json=_build_request())
    assert response.status_code == 200
    assert os.path.exists(db_path)


def test_like_creates_feedback(tmp_path, monkeypatch):
    db_path = str(tmp_path / "feedback.db")
    monkeypatch.setenv("FEEDBACK_DB_PATH", db_path)

    response = client.put("/api/feedback", json=_build_request(value="like"))
    assert response.status_code == 200
    payload = response.json()
    assert payload["value"] == "like"
    assert payload["target_type"] == "knowledge_node"
    assert payload["target_id"] == "candidate-1"


def test_update_like_to_dislike(tmp_path, monkeypatch):
    db_path = str(tmp_path / "feedback.db")
    monkeypatch.setenv("FEEDBACK_DB_PATH", db_path)

    client.put("/api/feedback", json=_build_request(value="like"))
    response = client.put("/api/feedback", json=_build_request(value="dislike"))
    assert response.status_code == 200
    assert response.json()["value"] == "dislike"

    listed = client.get("/api/feedback?anonymous_user_id=user-a").json()
    assert len(listed["feedbacks"]) == 1
    assert listed["feedbacks"][0]["value"] == "dislike"


def test_delete_feedback(tmp_path, monkeypatch):
    db_path = str(tmp_path / "feedback.db")
    monkeypatch.setenv("FEEDBACK_DB_PATH", db_path)

    client.put("/api/feedback", json=_build_request(value="like"))
    response = client.delete(
        "/api/feedback/knowledge_node/candidate-1?anonymous_user_id=user-a"
    )
    assert response.status_code == 204

    listed = client.get("/api/feedback?anonymous_user_id=user-a").json()
    assert listed["feedbacks"] == []


def test_feedback_persists_after_reconnect(tmp_path, monkeypatch):
    db_path = str(tmp_path / "feedback.db")
    monkeypatch.setenv("FEEDBACK_DB_PATH", db_path)

    client.put("/api/feedback", json=_build_request(value="like"))
    listed = client.get("/api/feedback?anonymous_user_id=user-a").json()
    assert len(listed["feedbacks"]) == 1


def test_user_isolation(tmp_path, monkeypatch):
    db_path = str(tmp_path / "feedback.db")
    monkeypatch.setenv("FEEDBACK_DB_PATH", db_path)

    client.put("/api/feedback", json=_build_request(anonymous_user_id="user-a", value="like"))
    client.put("/api/feedback", json=_build_request(anonymous_user_id="user-b", value="dislike"))

    user_a = client.get("/api/feedback?anonymous_user_id=user-a").json()
    user_b = client.get("/api/feedback?anonymous_user_id=user-b").json()
    assert len(user_a["feedbacks"]) == 1
    assert len(user_b["feedbacks"]) == 1
    assert user_a["feedbacks"][0]["value"] == "like"
    assert user_b["feedbacks"][0]["value"] == "dislike"


def test_invalid_target_type_returns_422():
    response = client.delete(
        "/api/feedback/invalid_type/candidate-1?anonymous_user_id=user-a"
    )
    assert response.status_code == 422


def test_invalid_value_returns_422():
    response = client.put("/api/feedback", json=_build_request(value="love"))
    assert response.status_code == 422


def test_surprise_level_must_be_in_range():
    response = client.put("/api/feedback", json=_build_request(surprise_level=1.5))
    assert response.status_code == 422


def test_no_duplicate_rows(tmp_path, monkeypatch):
    db_path = str(tmp_path / "feedback.db")
    monkeypatch.setenv("FEEDBACK_DB_PATH", db_path)

    for _ in range(3):
        response = client.put("/api/feedback", json=_build_request(value="like"))
        assert response.status_code == 200

    listed = client.get("/api/feedback?anonymous_user_id=user-a").json()
    assert len(listed["feedbacks"]) == 1


def test_get_returns_user_feedback(tmp_path, monkeypatch):
    db_path = str(tmp_path / "feedback.db")
    monkeypatch.setenv("FEEDBACK_DB_PATH", db_path)

    client.put("/api/feedback", json=_build_request(value="like"))
    response = client.get("/api/feedback?anonymous_user_id=user-a")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["feedbacks"]) == 1
    assert payload["feedbacks"][0]["target_id"] == "candidate-1"
    assert payload["feedbacks"][0]["value"] == "like"


def test_runtime_db_not_committed():
    import subprocess

    result = subprocess.run(
        ["git", "ls-files", "backend/data/feedback.db"],
        cwd="D:\\GitHub\\knowledge-wander",
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == ""
