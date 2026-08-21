"""Feedback persistence service backed by SQLite."""

from __future__ import annotations

import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.feedback import FeedbackRecord, FeedbackUpsertRequest, FeedbackValue

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


def _row_to_feedback(row: Any) -> FeedbackRecord:
    return FeedbackRecord(
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


def init_db(path: str | None = None) -> str:
    db_path = get_db_path(path)
    _ensure_parent(db_path)
    with sqlite3.connect(db_path, timeout=10) as connection:
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
    logger.info("Feedback DB initialized at %s", db_path)
    return db_path


def upsert_feedback(request: FeedbackUpsertRequest, path: str | None = None) -> FeedbackRecord:
    db_path = get_db_path(path)
    now = _now_iso()
    with sqlite3.connect(db_path, timeout=10) as connection:
        cursor = connection.execute(
            """
            INSERT INTO feedback (
                anonymous_user_id, target_type, target_id, target_label,
                target_domain, root_topic, value, surprise_level,
                generation_source, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(anonymous_user_id, target_type, target_id)
            DO UPDATE SET
                value = excluded.value,
                surprise_level = excluded.surprise_level,
                generation_source = excluded.generation_source,
                updated_at = excluded.updated_at
            """,
            (
                request.anonymous_user_id,
                request.target_type.value,
                request.target_id,
                request.target_label,
                request.target_domain,
                request.root_topic,
                request.value.value,
                request.surprise_level,
                request.generation_source,
                now,
                now,
            ),
        )
        connection.commit()
        row = connection.execute(
            "SELECT id, anonymous_user_id, target_type, target_id, target_label, target_domain, root_topic, value, surprise_level, generation_source, created_at, updated_at FROM feedback WHERE anonymous_user_id = ? AND target_type = ? AND target_id = ?",
            (
                request.anonymous_user_id,
                request.target_type.value,
                request.target_id,
            ),
        ).fetchone()
    try:
        from app.services.memory_service import refresh_memory
        refresh_memory(request.anonymous_user_id, path)
    except Exception as exc:
        logger.warning("Memory refresh after feedback upsert failed: %s", exc)
    return _row_to_feedback(row)


def delete_feedback(anonymous_user_id: str, target_type: str, target_id: str, path: str | None = None) -> None:
    db_path = get_db_path(path)
    with sqlite3.connect(db_path, timeout=10) as connection:
        connection.execute(
            "DELETE FROM feedback WHERE anonymous_user_id = ? AND target_type = ? AND target_id = ?",
            (anonymous_user_id, target_type, target_id),
        )
        connection.commit()
    try:
        from app.services.memory_service import refresh_memory
        refresh_memory(anonymous_user_id, path)
    except Exception as exc:
        logger.warning("Memory refresh after feedback delete failed: %s", exc)


def list_feedback(anonymous_user_id: str, path: str | None = None) -> list[FeedbackRecord]:
    db_path = get_db_path(path)
    with sqlite3.connect(db_path, timeout=10) as connection:
        rows = connection.execute(
            "SELECT id, anonymous_user_id, target_type, target_id, target_label, target_domain, root_topic, value, surprise_level, generation_source, created_at, updated_at FROM feedback WHERE anonymous_user_id = ?",
            (anonymous_user_id,),
        ).fetchall()
    return [_row_to_feedback(row) for row in rows]
