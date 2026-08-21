"""Request and response schemas for the explore endpoint."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.memory import AgentMetrics, MemoryProfileResponse


class ExploreRequest(BaseModel):
    """A topic and the user's preferred mock surprise level."""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1, max_length=120)
    surprise_level: float = Field(default=0.5, ge=0, le=1)
    anonymous_user_id: str | None = Field(default=None, max_length=64)
    use_memory: bool = Field(default=True)

    @field_validator("topic", mode="before")
    @classmethod
    def normalize_topic(cls, value: object) -> object:
        """Trim surrounding whitespace before length validation."""

        return value.strip() if isinstance(value, str) else value


class ExploreRoot(BaseModel):
    """The normalized starting point for an exploration."""

    id: str
    label: str


class ExploreNode(BaseModel):
    """A single cross-domain mock recommendation."""

    id: str
    label: str
    domain: str
    description: str
    connection: str
    surprise_score: float = Field(ge=0, le=1)


class ExploreResponseMetadata(BaseModel):
    """Extended metadata for explore responses."""

    model_config = ConfigDict(extra="forbid")

    memory: MemoryProfileResponse | None = None
    agent_metrics: AgentMetrics | None = None


class ExploreResponse(BaseModel):
    """The root topic and its candidate exploration nodes."""

    root: ExploreRoot
    nodes: list[ExploreNode]
    generation_source: str | None = None
    metadata: ExploreResponseMetadata | None = None
