"""Memory-aware candidate ranking and diversity guard."""

from __future__ import annotations

from typing import Any

from app.models.memory import MemoryProfile
from app.services.surprise_engine import Candidate, MIN_RELEVANCE


def _normalize(value: str) -> str:
    return value.strip().casefold()


def _matches_domain(candidate: Candidate, domain: str) -> bool:
    return domain in _normalize(candidate.domain) or _normalize(candidate.domain) in domain


def _matches_label(candidate: Candidate, concept: str) -> bool:
    return concept in _normalize(candidate.label) or _normalize(candidate.label) in concept


MEMORY_ADJUSTMENT_CAP = 0.10
PREFERRED_BOOST = 0.06
DISLIKED_PENALTY = 0.04
MIN_EVIDENCE = 2


def apply_memory_ranking(
    candidates: list[Candidate],
    memory: MemoryProfile | None,
) -> list[Candidate]:
    if memory is None or memory.evidence_count < MIN_EVIDENCE:
        return candidates

    preferred_domains = [_normalize(item) for item in memory.preferred_domains]
    disliked_domains = [_normalize(item) for item in memory.disliked_domains]
    liked_concepts = [_normalize(item) for item in memory.liked_concepts]
    disliked_concepts = [_normalize(item) for item in memory.disliked_concepts]

    adjusted: list[tuple[Candidate, float]] = []
    for candidate in candidates:
        adjustment = 0.0
        for domain in preferred_domains:
            if _matches_domain(candidate, domain):
                adjustment += PREFERRED_BOOST
                break
        for domain in disliked_domains:
            if _matches_domain(candidate, domain):
                adjustment -= DISLIKED_PENALTY
                break
        for concept in liked_concepts:
            if _matches_label(candidate, concept):
                adjustment += PREFERRED_BOOST * 0.5
                break
        for concept in disliked_concepts:
            if _matches_label(candidate, concept):
                adjustment -= DISLIKED_PENALTY * 0.5
                break
        adjustment = max(-MEMORY_ADJUSTMENT_CAP, min(MEMORY_ADJUSTMENT_CAP, adjustment))
        adjusted.append((candidate, adjustment))

    enriched = [
        Candidate(
            id=candidate.id,
            label=candidate.label,
            domain=candidate.domain,
            description=candidate.description,
            connection=candidate.connection,
            relevance=min(1.0, max(0.0, candidate.relevance + adjustment)),
            novelty=candidate.novelty,
            cross_domain=candidate.cross_domain,
        )
        for candidate, adjustment in adjusted
    ]
    return enriched


def enforce_diversity_guard(
    candidates: list[Candidate],
    memory: MemoryProfile | None,
    top_k: int = 6,
) -> list[Candidate]:
    if memory is None or memory.evidence_count < MIN_EVIDENCE:
        return candidates[:top_k]

    preferred_domains = [_normalize(item) for item in memory.preferred_domains]
    if not preferred_domains:
        return candidates[:top_k]

    selected: list[Candidate] = []
    outside_count = 0
    for candidate in candidates:
        if len(selected) >= top_k:
            break
        selected.append(candidate)
        if not any(_matches_domain(candidate, domain) for domain in preferred_domains):
            outside_count += 1

    if outside_count < 2 and len(candidates) > top_k:
        needed = 2 - outside_count
        added = 0
        for candidate in candidates:
            if added >= needed:
                break
            if candidate in selected:
                continue
            if not any(_matches_domain(candidate, domain) for domain in preferred_domains):
                selected.append(candidate)
                added += 1

    return selected[:top_k]
