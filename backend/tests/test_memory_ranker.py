"""Memory ranker and diversity guard tests."""

from app.models.memory import MemoryProfile
from app.services.memory_ranker import apply_memory_ranking, enforce_diversity_guard
from app.services.surprise_engine import Candidate


def _candidate(
    label: str,
    domain: str,
    relevance: float = 0.5,
    novelty: float = 0.5,
    cross_domain: float = 0.5,
) -> Candidate:
    return Candidate(
        id=label,
        label=label,
        domain=domain,
        description="",
        connection="",
        relevance=relevance,
        novelty=novelty,
        cross_domain=cross_domain,
    )


def test_apply_memory_ranking_boosts_preferred_domain():
    candidates = [
        _candidate("A", "建筑学", relevance=0.5),
        _candidate("B", "计算机科学", relevance=0.5),
    ]
    memory = MemoryProfile(
        anonymous_user_id="user-a",
        preferred_domains=["建筑学"],
        disliked_domains=[],
        liked_concepts=[],
        disliked_concepts=[],
        preferred_surprise_level=0.5,
        evidence_count=5,
        updated_at="2024-01-01T00:00:00+00:00",
    )

    ranked = apply_memory_ranking(candidates, memory)
    assert ranked[0].relevance > ranked[1].relevance
    assert ranked[0].label == "A"


def test_apply_memory_ranking_penalizes_disliked_domain():
    candidates = [
        _candidate("A", "动物学", relevance=0.5),
        _candidate("B", "计算机科学", relevance=0.5),
    ]
    memory = MemoryProfile(
        anonymous_user_id="user-a",
        preferred_domains=[],
        disliked_domains=["动物学"],
        liked_concepts=[],
        disliked_concepts=[],
        preferred_surprise_level=0.5,
        evidence_count=5,
        updated_at="2024-01-01T00:00:00+00:00",
    )

    ranked = apply_memory_ranking(candidates, memory)
    assert ranked[1].relevance > ranked[0].relevance
    assert ranked[1].label == "B"


def test_apply_memory_ranking_respects_evidence_threshold():
    candidates = [_candidate("A", "建筑学", relevance=0.5)]
    memory = MemoryProfile(
        anonymous_user_id="user-a",
        preferred_domains=["建筑学"],
        disliked_domains=[],
        liked_concepts=[],
        disliked_concepts=[],
        preferred_surprise_level=0.5,
        evidence_count=1,
        updated_at="2024-01-01T00:00:00+00:00",
    )

    ranked = apply_memory_ranking(candidates, memory)
    assert ranked[0].relevance == 0.5


def test_apply_memory_ranking_caps_adjustment():
    candidates = [
        _candidate("A", "建筑学", relevance=0.5),
        _candidate("B", "设计学", relevance=0.5),
        _candidate("C", "计算机科学", relevance=0.5),
    ]
    memory = MemoryProfile(
        anonymous_user_id="user-a",
        preferred_domains=["建筑学", "设计学"],
        disliked_domains=["计算机科学"],
        liked_concepts=[],
        disliked_concepts=[],
        preferred_surprise_level=0.5,
        evidence_count=5,
        updated_at="2024-01-01T00:00:00+00:00",
    )

    ranked = apply_memory_ranking(candidates, memory)
    assert all(candidate.relevance <= 1.0 for candidate in ranked)
    assert all(candidate.relevance >= 0.0 for candidate in ranked)


def test_enforce_diversity_guard_keeps_outside_candidates():
    candidates = [
        _candidate("A", "建筑学", relevance=0.9),
        _candidate("B", "建筑学", relevance=0.8),
        _candidate("C", "计算机科学", relevance=0.7),
        _candidate("D", "计算机科学", relevance=0.6),
        _candidate("E", "心理学", relevance=0.5),
        _candidate("F", "心理学", relevance=0.4),
    ]
    memory = MemoryProfile(
        anonymous_user_id="user-a",
        preferred_domains=["建筑学"],
        disliked_domains=[],
        liked_concepts=[],
        disliked_concepts=[],
        preferred_surprise_level=0.5,
        evidence_count=5,
        updated_at="2024-01-01T00:00:00+00:00",
    )

    selected = enforce_diversity_guard(candidates, memory, top_k=6)
    outside = [c for c in selected if c.domain != "建筑学"]
    assert len(outside) >= 2


def test_enforce_diversity_guard_respects_evidence_threshold():
    candidates = [_candidate("A", "建筑学", relevance=0.5)]
    memory = MemoryProfile(
        anonymous_user_id="user-a",
        preferred_domains=["建筑学"],
        disliked_domains=[],
        liked_concepts=[],
        disliked_concepts=[],
        preferred_surprise_level=0.5,
        evidence_count=1,
        updated_at="2024-01-01T00:00:00+00:00",
    )

    selected = enforce_diversity_guard(candidates, memory, top_k=6)
    assert len(selected) == 1
