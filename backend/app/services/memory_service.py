"""Memory persistence and extraction service backed by SQLite."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.feedback import FeedbackRecord, FeedbackValue
from app.models.memory import MemoryProfile

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = REPO_ROOT / "data" / "feedback.db"
_DEFAULT_DB_PATH_STR = str(DEFAULT_DB_PATH)


def _build_db_path(explicit_path: str | None = None) -> str:
    if explicit_path:
        return explicit_path
    env_path = os.getenv("FEEDBACK_DB_PATH")
    if env_path:
        return env_path
    return _DEFAULT_DB_PATH_STR


def _ensure_parent(path: str) -> None:
    parent = Path(path).resolve().parent
    parent.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_db_path(explicit_path: str | None = None) -> str:
    return _build_db_path(explicit_path)


def init_memory_db(path: str | None = None) -> str:
    db_path = get_db_path(path)
    _ensure_parent(db_path)
    with sqlite3.connect(db_path, timeout=10) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS user_memory (
                anonymous_user_id TEXT PRIMARY KEY,
                preferred_domains_json TEXT NOT NULL DEFAULT '[]',
                disliked_domains_json TEXT NOT NULL DEFAULT '[]',
                liked_concepts_json TEXT NOT NULL DEFAULT '[]',
                disliked_concepts_json TEXT NOT NULL DEFAULT '[]',
                preferred_surprise_level REAL NOT NULL DEFAULT 0.5,
                evidence_count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT '',
                memory_signature TEXT NOT NULL DEFAULT '',
                feedback_updated_at TEXT NOT NULL DEFAULT ''
            )
            """
        )
        columns = {row[1] for row in connection.execute("PRAGMA table_info(user_memory)").fetchall()}
        if "memory_signature" not in columns:
            connection.execute(
                "ALTER TABLE user_memory ADD COLUMN memory_signature TEXT NOT NULL DEFAULT ''"
            )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                anonymous_user_id TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                target_label TEXT NOT NULL,
                target_domain TEXT NOT NULL,
                root_topic TEXT NOT NULL,
                value TEXT NOT NULL,
                surprise_level REAL NOT NULL,
                generation_source TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_feedback_user_target
            ON feedback (anonymous_user_id, target_type, target_id)
            """
        )
        connection.commit()
    return db_path


def _build_signature(profile: MemoryProfile) -> str:
    payload = (
        profile.preferred_domains
        + profile.disliked_domains
        + profile.liked_concepts
        + profile.disliked_concepts
    )
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


def _aggregate_feedback(feedbacks: list[FeedbackRecord]) -> MemoryProfile:
    preferred_domains: dict[str, int] = {}
    disliked_domains: dict[str, int] = {}
    liked_concepts: dict[str, int] = {}
    disliked_concepts: dict[str, int] = {}
    surprise_sum = 0.0
    surprise_count = 0

    for feedback in feedbacks:
        if feedback.value == FeedbackValue.LIKE:
            if feedback.target_domain:
                preferred_domains[feedback.target_domain] = preferred_domains.get(feedback.target_domain, 0) + 1
            liked_concepts[feedback.target_label] = liked_concepts.get(feedback.target_label, 0) + 1
            surprise_sum += feedback.surprise_level
            surprise_count += 1
        else:
            if feedback.target_domain:
                disliked_domains[feedback.target_domain] = disliked_domains.get(feedback.target_domain, 0) + 1
            disliked_concepts[feedback.target_label] = disliked_concepts.get(feedback.target_label, 0) + 1

    preferred_surprise_level = (surprise_sum / surprise_count) if surprise_count else 0.5

    def top_items(mapping: dict[str, int], limit: int) -> list[str]:
        return [item for item, _ in sorted(mapping.items(), key=lambda item: (-item[1], item[0]))[:limit]]

    profile = MemoryProfile(
        anonymous_user_id=feedbacks[0].anonymous_user_id if feedbacks else "",
        preferred_domains=top_items(preferred_domains, 3),
        disliked_domains=top_items(disliked_domains, 3),
        liked_concepts=top_items(liked_concepts, 5),
        disliked_concepts=top_items(disliked_concepts, 5),
        preferred_surprise_level=round(min(1.0, max(0.0, preferred_surprise_level)), 2),
        evidence_count=len(feedbacks),
        updated_at=_now_iso(),
    )
    profile.memory_signature = _build_signature(profile)
    return profile


def _row_to_profile(row: Any) -> MemoryProfile:
    return MemoryProfile(
        anonymous_user_id=row[0],
        preferred_domains=json.loads(row[1] or "[]"),
        disliked_domains=json.loads(row[2] or "[]"),
        liked_concepts=json.loads(row[3] or "[]"),
        disliked_concepts=json.loads(row[4] or "[]"),
        preferred_surprise_level=row[5],
        evidence_count=row[6],
        updated_at=row[7] or "",
        memory_signature=row[8] or "",
        feedback_updated_at=row[9] or "",
    )


def get_memory(anonymous_user_id: str, path: str | None = None) -> MemoryProfile | None:
    db_path = init_memory_db(path)
    with sqlite3.connect(db_path, timeout=10) as connection:
        row = connection.execute(
            "SELECT anonymous_user_id, preferred_domains_json, disliked_domains_json, liked_concepts_json, disliked_concepts_json, preferred_surprise_level, evidence_count, updated_at, memory_signature, feedback_updated_at FROM user_memory WHERE anonymous_user_id = ?",
            (anonymous_user_id,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_profile(row)


def refresh_memory(anonymous_user_id: str, path: str | None = None) -> MemoryProfile:
    db_path = init_memory_db(path)
    with sqlite3.connect(db_path, timeout=10) as connection:
        rows = connection.execute(
            "SELECT id, anonymous_user_id, target_type, target_id, target_label, target_domain, root_topic, value, surprise_level, generation_source, created_at, updated_at FROM feedback WHERE anonymous_user_id = ?",
            (anonymous_user_id,),
        ).fetchall()
    feedbacks = [
        FeedbackRecord(
            id=row[0],
            anonymous_user_id=row[1],
            target_type=row[2],
            target_id=row[3],
            target_label=row[4],
            target_domain=row[5],
            root_topic=row[6],
            value=row[7],
            surprise_level=row[8],
            generation_source=row[9],
            created_at=row[10],
            updated_at=row[11],
        )
        for row in rows
    ]
    profile = _aggregate_feedback(feedbacks)
    profile.anonymous_user_id = anonymous_user_id
    now = _now_iso()
    with sqlite3.connect(db_path, timeout=10) as connection:
        connection.execute(
            """
            INSERT INTO user_memory (
                anonymous_user_id, preferred_domains_json, disliked_domains_json,
                liked_concepts_json, disliked_concepts_json, preferred_surprise_level,
                evidence_count, feedback_updated_at, updated_at, memory_signature
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(anonymous_user_id) DO UPDATE SET
                preferred_domains_json = excluded.preferred_domains_json,
                disliked_domains_json = excluded.disliked_domains_json,
                liked_concepts_json = excluded.liked_concepts_json,
                disliked_concepts_json = excluded.disliked_concepts_json,
                preferred_surprise_level = excluded.preferred_surprise_level,
                evidence_count = excluded.evidence_count,
                feedback_updated_at = excluded.feedback_updated_at,
                updated_at = excluded.updated_at,
                memory_signature = excluded.memory_signature
            """,
            (
                anonymous_user_id,
                json.dumps(profile.preferred_domains, ensure_ascii=False),
                json.dumps(profile.disliked_domains, ensure_ascii=False),
                json.dumps(profile.liked_concepts, ensure_ascii=False),
                json.dumps(profile.disliked_concepts, ensure_ascii=False),
                profile.preferred_surprise_level,
                profile.evidence_count,
                now,
                now,
                profile.memory_signature,
            ),
        )
        connection.commit()
    return profile


def ensure_memory(anonymous_user_id: str, path: str | None = None) -> MemoryProfile | None:
    profile = get_memory(anonymous_user_id, path)
    if profile is not None and profile.evidence_count > 0:
        return profile

    rebuilt = refresh_memory(anonymous_user_id, path)
    return rebuilt if rebuilt.evidence_count > 0 else None
