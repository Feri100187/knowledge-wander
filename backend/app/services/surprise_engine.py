"""Surprise Engine for Knowledge Wander."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.explore import ExploreNode


@dataclass
class Candidate:
    id: str
    label: str
    domain: str
    description: str
    connection: str
    relevance: float
    novelty: float
    cross_domain: float

    @property
    def surprise_score(self) -> float:
        return round(min(1.0, max(0.0, self.novelty * 0.55 + self.cross_domain * 0.45)), 2)

    def ranking_score(self, requested_surprise_level: float) -> float:
        surprise_match = 1.0 - abs(self.surprise_score - requested_surprise_level)
        return self.relevance * 0.5 + surprise_match * 0.5


MIN_RELEVANCE = 0.25


def select_top_candidates(
    candidates: list[Candidate],
    surprise_level: float,
    top_k: int = 6,
) -> list[Candidate]:
    filtered = [c for c in candidates if c.relevance >= MIN_RELEVANCE]
    ranked = sorted(
        filtered,
        key=lambda c: (
            -c.ranking_score(surprise_level),
            -c.relevance,
            c.id,
        ),
    )
    return ranked[:top_k]


def to_explore_nodes(candidates: list[Candidate]) -> list[ExploreNode]:
    return [
        ExploreNode(
            id=c.id,
            label=c.label,
            domain=c.domain,
            description=c.description,
            connection=c.connection,
            surprise_score=c.surprise_score,
        )
        for c in candidates
    ]
