"""Lightweight exploration agent orchestrator."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from app.models.explore import (
    ExploreRequest,
    ExploreResponse,
    ExploreRoot,
    ExploreResponseMetadata,
)
from app.models.feedback import FeedbackRecord
from app.models.memory import AgentMetrics, MemoryProfile, MemoryProfileResponse
from app.services.llm_service import LLMGenerationResult, _build_prompt, _normalize_label
from app.services.memory_ranker import apply_memory_ranking, enforce_diversity_guard
from app.services.memory_service import ensure_memory, get_memory, refresh_memory
from app.services.surprise_engine import Candidate, select_top_candidates, to_explore_nodes

logger = logging.getLogger(__name__)


def _get_llm_service():
    from app.services.explore_service import get_llm_service
    return get_llm_service()


get_llm_service = _get_llm_service


def _build_memory_context(profile: MemoryProfile | None) -> str:
    if profile is None or profile.evidence_count < 2:
        return ""

    parts = [
        "## User Memory",
        "",
        "The following is soft preference evidence, not a hard constraint.",
        "",
    ]
    if profile.preferred_domains:
        parts.append("Preferred domains:")
        for domain in profile.preferred_domains:
            parts.append(f"- {domain}")
        parts.append("")
    if profile.disliked_domains:
        parts.append("Less preferred domains:")
        for domain in profile.disliked_domains:
            parts.append(f"- {domain}")
        parts.append("")
    if profile.liked_concepts:
        parts.append("Liked concepts:")
        for concept in profile.liked_concepts[:5]:
            parts.append(f"- {concept}")
        parts.append("")
    if profile.disliked_concepts:
        parts.append("Less liked concepts:")
        for concept in profile.disliked_concepts[:5]:
            parts.append(f"- {concept}")
        parts.append("")
    parts.extend(
        [
            "Important:",
            "- Use this only as a gentle personalization signal.",
            "- Do not simply repeat preferred domains.",
            "- Preserve meaningful discovery outside known preferences.",
            "- At least 40% of generated candidates should explore outside preferred domains.",
            "- A disliked domain is not absolutely forbidden if it forms a genuinely valuable unexpected connection.",
        ]
    )
    return "\n".join(parts)


def _build_prompt_with_memory(topic: str, candidate_count: int, memory_context: str) -> str:
    prompt = _build_prompt(topic, candidate_count, memory_context if memory_context else "")
    return prompt


def _extract_feedbacks_for_topic(
    feedbacks: list[FeedbackRecord],
    root_topic: str,
) -> list[FeedbackRecord]:
    normalized_root = _normalize_label(root_topic)
    return [f for f in feedbacks if _normalize_label(f.root_topic) == normalized_root]


def _build_memory_profile_response(
    anonymous_user_id: str,
) -> tuple[MemoryProfileResponse | None, float]:
    start = time.perf_counter()
    try:
        profile = get_memory(anonymous_user_id)
        if profile is None:
            return MemoryProfileResponse(available=False, profile=None), time.perf_counter() - start
        return MemoryProfileResponse(available=True, profile=profile), time.perf_counter() - start
    except Exception as exc:
        logger.warning("Memory retrieval failed: %s", exc)
        return None, time.perf_counter() - start


def run_exploration(request: ExploreRequest) -> tuple[ExploreResponse, AgentMetrics | None]:
    from app.services.explore_service import _topic_id
    from app.services.explore_service import (
        _fallback_candidates,
        _supplement_candidates_with_fallback,
        _update_generation_source,
    )

    memory_retrieval_ms = 0.0
    llm_latency_ms = 0.0
    total_start = time.perf_counter()
    prompt_tokens = None
    completion_tokens = None
    total_tokens = None
    cache_hit = False
    memory: MemoryProfile | None = None
    memory_applied = False

    if request.anonymous_user_id and request.use_memory:
        try:
            memory_response, memory_retrieval_ms = _build_memory_profile_response(
                request.anonymous_user_id
            )
        except Exception:
            memory_response = None
    else:
        memory_response = None

    if memory_response is not None and memory_response.available:
        memory = memory_response.profile

    topic = request.topic
    candidate_count = 18
    memory_context = _build_memory_context(memory)
    memory_context_chars = len(memory_context.encode("utf-8"))
    root_id = _topic_id(topic)
    fallback = _fallback_candidates(topic, root_id)

    llm_candidates: list[Candidate] | None = None
    fallback_used = False
    memory_signature = memory.memory_signature if memory else None
    generation_result = None
    service = get_llm_service()
    if service is None:
        fallback_used = True
    else:
        try:
            generation_result = service.get_candidates(
                topic,
                memory_context=memory_context,
                memory_signature=memory_signature,
            )
            llm_latency_ms = generation_result.latency_ms
            cache_hit = generation_result.cache_hit
            prompt_tokens = generation_result.prompt_tokens
            completion_tokens = generation_result.completion_tokens
            total_tokens = generation_result.total_tokens
            if generation_result.candidates:
                llm_candidates = [
                    Candidate(
                        id=_normalize_label(c.label),
                        label=c.label,
                        domain=c.domain,
                        description=c.description,
                        connection=c.connection,
                        relevance=c.relevance,
                        novelty=c.novelty,
                        cross_domain=c.cross_domain,
                    )
                    for c in generation_result.candidates
                ]
        except Exception:
            llm_candidates = None
            fallback_used = True

    raw_llm_candidates = llm_candidates
    if llm_candidates is None or len(llm_candidates) < 6:
        fallback_used = True
        selected = select_top_candidates(fallback, request.surprise_level)
        selected = selected[:6]
        generation_source = "fallback"
    elif len(llm_candidates) >= 12:
        if memory is not None and memory.evidence_count >= 2:
            llm_candidates = apply_memory_ranking(llm_candidates, memory)
            memory_applied = True
        selected = select_top_candidates(llm_candidates, request.surprise_level)
        selected = enforce_diversity_guard(selected, memory)
        generation_source = "llm"
    else:
        llm_candidates, _fallback_added = _supplement_candidates_with_fallback(
            llm_candidates,
            fallback,
            request.surprise_level,
            target_count=12,
        )
        if memory is not None and memory.evidence_count >= 2:
            llm_candidates = apply_memory_ranking(llm_candidates, memory)
            memory_applied = True
        selected = select_top_candidates(llm_candidates, request.surprise_level)
        selected = enforce_diversity_guard(selected, memory)
        generation_source = "llm+fallback"

    selected, fallback_added = _supplement_candidates_with_fallback(
        selected,
        fallback,
        request.surprise_level,
    )
    generation_source = _update_generation_source(generation_source, fallback_added)
    nodes = to_explore_nodes(selected)
    total_latency_ms = time.perf_counter() - total_start
    changed_nodes_vs_baseline = 0
    exploration_ratio = 0.0
    if memory is not None and memory.evidence_count >= 2 and raw_llm_candidates:
        try:
            baseline = select_top_candidates(raw_llm_candidates, request.surprise_level)
            baseline_ids = {c.id for c in baseline[:6]}
            selected_ids = {c.id for c in selected}
            changed_nodes_vs_baseline = len(baseline_ids - selected_ids)
            if selected:
                preferred_domains = [_normalize_label(d) for d in memory.preferred_domains]
                outside = sum(
                    1
                    for c in selected
                    if not any(
                        _normalize_label(c.domain) in pd or pd in _normalize_label(c.domain)
                        for pd in preferred_domains
                    )
                )
                exploration_ratio = outside / len(selected)
        except Exception:
            changed_nodes_vs_baseline = 0
            exploration_ratio = 0.0

    metrics = AgentMetrics(
        memory_retrieval_ms=round(memory_retrieval_ms * 1000, 2),
        llm_latency_ms=round(llm_latency_ms, 2),
        total_latency_ms=round(total_latency_ms * 1000, 2),
        candidate_cache_hit=cache_hit,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        memory_context_chars=memory_context_chars,
        changed_nodes_vs_baseline=changed_nodes_vs_baseline,
        exploration_ratio=round(exploration_ratio, 2),
    )

    memory_response_for_metadata = (
        MemoryProfileResponse(available=memory is not None, profile=memory)
        if memory is not None
        else MemoryProfileResponse(available=False, profile=None)
    )
    response = ExploreResponse(
        root=ExploreRoot(id=root_id, label=request.topic),
        nodes=nodes,
        generation_source=generation_source,
        metadata=ExploreResponseMetadata(
            memory=memory_response_for_metadata,
            agent_metrics=metrics,
        ),
    )

    logger.info(
        "Agent completed: memory_applied=%s evidence=%d changed=%d exploration_ratio=%.2f",
        memory_applied,
        memory.evidence_count if memory else 0,
        changed_nodes_vs_baseline,
        exploration_ratio,
    )
    return response, metrics
