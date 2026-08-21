"""Memory profile schemas for personalized exploration."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MemoryProfile(BaseModel):
    """Derived preference profile built from user feedback."""

    model_config = ConfigDict(extra="forbid")

    anonymous_user_id: str
    preferred_domains: list[str] = Field(default_factory=list, max_length=3)
    disliked_domains: list[str] = Field(default_factory=list, max_length=3)
    liked_concepts: list[str] = Field(default_factory=list, max_length=5)
    disliked_concepts: list[str] = Field(default_factory=list, max_length=5)
    preferred_surprise_level: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence_count: int = Field(default=0, ge=0)
    updated_at: str = ""
    memory_signature: str = ""
    feedback_updated_at: str = ""


class MemoryProfileResponse(BaseModel):
    """Public memory profile for API responses."""

    model_config = ConfigDict(extra="forbid")

    available: bool
    profile: MemoryProfile | None = None


class AgentMetrics(BaseModel):
    """Lightweight agent execution metrics."""

    model_config = ConfigDict(extra="forbid")

    memory_retrieval_ms: float = 0.0
    llm_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    candidate_cache_hit: bool = False
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    memory_context_chars: int = 0
    changed_nodes_vs_baseline: int = 0
    exploration_ratio: float = Field(default=0.0, ge=0.0, le=1.0)


class AgentPlanStep(BaseModel):
    """Single step in the lightweight agent plan."""

    model_config = ConfigDict(extra="forbid")

    step: str
    status: str
