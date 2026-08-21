"""Memory service tests."""

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.feedback import FeedbackRecord, FeedbackValue
from app.models.memory import MemoryProfile
from app.services.memory_service import (
    _aggregate_feedback,
    _build_signature,
    ensure_memory,
    get_memory,
    init_memory_db,
    refresh_memory,
)

client = TestClient(app)


def _build_feedback(
    anonymous_user_id: str = "memory-user",
    target_label: str = "建筑空间设计",
    target_domain: str = "建筑学",
    root_topic: str = "游戏开发",
    value: str = "like",
    surprise_level: float = 0.5,
    target_id: str = "candidate-1",
) -> dict:
    return {
        "anonymous_user_id": anonymous_user_id,
        "target_type": "knowledge_node",
        "target_id": target_id,
        "target_label": target_label,
        "target_domain": target_domain,
        "root_topic": root_topic,
        "value": value,
        "surprise_level": surprise_level,
        "generation_source": "llm",
    }


def test_init_memory_db_creates_table(tmp_path, monkeypatch):
    db_path = str(tmp_path / "memory.db")
    monkeypatch.setenv("FEEDBACK_DB_PATH", db_path)

    result = init_memory_db(db_path)
    assert result == db_path

    response = client.get("/api/memory?anonymous_user_id=memory-user")
    assert response.status_code == 200
    assert response.json() == {"available": False, "profile": None}


def test_get_memory_returns_none_when_empty(tmp_path, monkeypatch):
    db_path = str(tmp_path / "memory.db")
    monkeypatch.setenv("FEEDBACK_DB_PATH", db_path)
    init_memory_db(db_path)

    assert get_memory("memory-user", db_path) is None


def test_get_memory_upgrades_existing_feedback_only_database(tmp_path, monkeypatch):
    """A pre-Milestone-7 database must gain the memory table automatically."""

    from app.services.feedback_service import init_db

    db_path = str(tmp_path / "feedback-only.db")
    monkeypatch.setenv("FEEDBACK_DB_PATH", db_path)
    init_db(db_path)

    assert get_memory("memory-user", db_path) is None

    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert "feedback" in tables
    assert "user_memory" in tables


def test_ensure_memory_rebuilds_profile_from_existing_feedback(tmp_path, monkeypatch):
    """Feedback from an older demo database remains usable after the schema upgrade."""

    from app.services.feedback_service import init_db

    db_path = str(tmp_path / "legacy-feedback.db")
    monkeypatch.setenv("FEEDBACK_DB_PATH", db_path)
    init_db(db_path)

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO feedback (
                anonymous_user_id, target_type, target_id, target_label,
                target_domain, root_topic, value, surprise_level,
                generation_source, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-user",
                "knowledge_node",
                "legacy-node",
                "视觉文化",
                "文化研究",
                "摄影史",
                "like",
                0.6,
                "fallback",
                "2026-08-20T00:00:00+00:00",
                "2026-08-20T00:00:00+00:00",
            ),
        )
        connection.commit()

    profile = ensure_memory("legacy-user", db_path)

    assert profile is not None
    assert profile.evidence_count == 1
    assert profile.preferred_domains == ["文化研究"]


def test_refresh_memory_creates_profile(tmp_path, monkeypatch):
    db_path = str(tmp_path / "memory.db")
    monkeypatch.setenv("FEEDBACK_DB_PATH", db_path)
    init_memory_db(db_path)

    client.put("/api/feedback", json=_build_feedback(value="like", target_id="candidate-1"))
    client.put("/api/feedback", json=_build_feedback(value="like", target_id="candidate-2"))
    client.put(
        "/api/feedback",
        json=_build_feedback(
            value="dislike", target_label="企鹅", target_domain="动物学", target_id="candidate-3"
        ),
    )

    profile = refresh_memory("memory-user", db_path)
    assert profile.evidence_count == 3
    assert "建筑学" in profile.preferred_domains
    assert "动物学" in profile.disliked_domains
    assert "建筑空间设计" in profile.liked_concepts
    assert "企鹅" in profile.disliked_concepts
    assert profile.memory_signature


def test_ensure_memory_returns_existing_profile(tmp_path, monkeypatch):
    db_path = str(tmp_path / "memory.db")
    monkeypatch.setenv("FEEDBACK_DB_PATH", db_path)
    init_memory_db(db_path)

    client.put("/api/feedback", json=_build_feedback(value="like"))

    first = ensure_memory("memory-user", db_path)
    second = ensure_memory("memory-user", db_path)

    assert first.memory_signature == second.memory_signature
    assert second.evidence_count == 1


def test_memory_api_returns_profile(tmp_path, monkeypatch):
    db_path = str(tmp_path / "memory.db")
    monkeypatch.setenv("FEEDBACK_DB_PATH", db_path)
    init_memory_db(db_path)

    client.put("/api/feedback", json=_build_feedback(value="like", target_id="candidate-1"))
    client.put("/api/feedback", json=_build_feedback(value="like", target_id="candidate-2"))

    response = client.get("/api/memory?anonymous_user_id=memory-user")
    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["profile"]["evidence_count"] == 2
    assert "建筑学" in payload["profile"]["preferred_domains"]


def test_memory_api_without_user_returns_unavailable():
    response = client.get("/api/memory")
    assert response.status_code == 200
    assert response.json() == {"available": False, "profile": None}


def test_build_signature_changes_with_preferences():
    profile_a = MemoryProfile(
        anonymous_user_id="user-a",
        preferred_domains=["建筑学"],
        disliked_domains=[],
        liked_concepts=["建筑空间设计"],
        disliked_concepts=[],
        preferred_surprise_level=0.5,
        evidence_count=1,
        updated_at="2024-01-01T00:00:00+00:00",
    )
    profile_b = MemoryProfile(
        anonymous_user_id="user-a",
        preferred_domains=["建筑学", "设计学"],
        disliked_domains=[],
        liked_concepts=["建筑空间设计"],
        disliked_concepts=[],
        preferred_surprise_level=0.5,
        evidence_count=1,
        updated_at="2024-01-01T00:00:00+00:00",
    )

    assert _build_signature(profile_a) != _build_signature(profile_b)


def test_aggregate_feedback_computes_preferences():
    feedbacks = [
        FeedbackRecord(
            id=1,
            anonymous_user_id="user-a",
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
        ),
        FeedbackRecord(
            id=2,
            anonymous_user_id="user-a",
            target_type="knowledge_node",
            target_id="2",
            target_label="建筑空间设计",
            target_domain="建筑学",
            root_topic="游戏开发",
            value="like",
            surprise_level=0.6,
            generation_source="llm",
            created_at="2024-01-01T00:00:00+00:00",
            updated_at="2024-01-01T00:00:00+00:00",
        ),
        FeedbackRecord(
            id=3,
            anonymous_user_id="user-a",
            target_type="knowledge_node",
            target_id="3",
            target_label="企鹅",
            target_domain="动物学",
            root_topic="游戏开发",
            value="dislike",
            surprise_level=0.5,
            generation_source="llm",
            created_at="2024-01-01T00:00:00+00:00",
            updated_at="2024-01-01T00:00:00+00:00",
        ),
    ]

    profile = _aggregate_feedback(feedbacks)
    assert profile.evidence_count == 3
    assert "建筑学" in profile.preferred_domains
    assert "动物学" in profile.disliked_domains
    assert "建筑空间设计" in profile.liked_concepts
    assert "企鹅" in profile.disliked_concepts
    assert abs(profile.preferred_surprise_level - 0.55) < 0.01


def test_aggregate_feedback_empty_list():
    profile = _aggregate_feedback([])
    assert profile.evidence_count == 0
    assert profile.preferred_surprise_level == 0.5
    assert profile.memory_signature
