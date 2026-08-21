"""Schemas for the feedback system."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FeedbackTargetType(str, Enum):
    """Supported feedback target types."""

    KNOWLEDGE_NODE = "knowledge_node"
    BOOK = "book"


class FeedbackValue(str, Enum):
    """Supported feedback values."""

    LIKE = "like"
    DISLIKE = "dislike"


class FeedbackUpsertRequest(BaseModel):
    """Upsert a feedback record for the current anonymous user."""

    model_config = ConfigDict(extra="forbid")

    anonymous_user_id: str = Field(min_length=1, max_length=128)
    target_type: FeedbackTargetType
    target_id: str = Field(min_length=1, max_length=128)
    target_label: str = Field(min_length=1, max_length=120)
    target_domain: str = Field(min_length=1, max_length=120)
    root_topic: str = Field(min_length=1, max_length=120)
    value: FeedbackValue
    surprise_level: float = Field(default=0.5, ge=0.0, le=1.0)
    generation_source: str | None = None


class FeedbackRecord(FeedbackUpsertRequest):
    """A persisted feedback record."""

    id: int
    created_at: str
    updated_at: str


class FeedbackListResponse(BaseModel):
    """Active feedback records for a user."""

    model_config = ConfigDict(extra="forbid")

    feedbacks: list[FeedbackRecord]
