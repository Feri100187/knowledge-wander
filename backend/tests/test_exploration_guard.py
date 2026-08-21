"""Regression tests for score calibration and empty-graph protection."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.models.explore import ExploreRequest
from app.models.llm import LLMCandidate
from app.models.memory import MemoryProfile, MemoryProfileResponse
from app.services.exploration_agent import run_exploration
from app.services.explore_service import explore_topic
from app.services.llm_service import LLMGenerationResult, _build_prompt
from app.services.surprise_engine import Candidate


def _llm_candidate(
    index: int,
    *,
    relevance: float,
    novelty: float = 0.5,
    cross_domain: float = 0.5,
    label: str | None = None,
) -> LLMCandidate:
    return LLMCandidate(
        label=label or f"LLM-{index}",
        domain="测试领域",
        description="一句简短描述。",
        connection="一句具体连接。",
        relevance=relevance,
        novelty=novelty,
        cross_domain=cross_domain,
    )


def _generation_result(candidates: list[LLMCandidate]) -> LLMGenerationResult:
    return LLMGenerationResult(
        candidates=candidates,
        cache_hit=False,
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
        latency_ms=1.0,
    )


def _fallback_candidate(
    index: int,
    *,
    candidate_id: str | None = None,
    label: str | None = None,
    relevance: float = 0.8,
    novelty: float = 0.5,
    cross_domain: float = 0.5,
) -> Candidate:
    return Candidate(
        id=candidate_id or f"fallback-{index}",
        label=label or f"Fallback-{index}",
        domain="备用领域",
        description="备用候选描述。",
        connection="备用候选连接。",
        relevance=relevance,
        novelty=novelty,
        cross_domain=cross_domain,
    )


def _fallback_pool(count: int = 8) -> list[Candidate]:
    return [_fallback_candidate(index) for index in range(count)]


def _explore_without_memory(
    llm_candidates: list[LLMCandidate],
    fallback: list[Candidate],
    surprise_level: float = 0.5,
):
    service = MagicMock()
    service.get_candidates.return_value = _generation_result(llm_candidates)
    with patch("app.services.explore_service.get_llm_service", return_value=service):
        with patch(
            "app.services.explore_service._fallback_candidates",
            return_value=fallback,
        ):
            return explore_topic(
                ExploreRequest(
                    topic="测试",
                    surprise_level=surprise_level,
                    use_memory=False,
                )
            )


def test_all_low_relevance_llm_candidates_still_return_six_nodes() -> None:
    response = _explore_without_memory(
        [_llm_candidate(index, relevance=0.10) for index in range(12)],
        _fallback_pool(),
    )

    assert len(response.nodes) == 6
    assert response.generation_source == "llm+fallback"
    assert all(node.label.startswith("Fallback-") for node in response.nodes)


def test_two_eligible_llm_candidates_are_kept_and_four_fallbacks_added() -> None:
    llm_candidates = [
        _llm_candidate(0, relevance=0.5),
        _llm_candidate(1, relevance=0.5),
        *[_llm_candidate(index, relevance=0.10) for index in range(2, 12)],
    ]

    response = _explore_without_memory(llm_candidates, _fallback_pool())

    assert len(response.nodes) == 6
    assert response.generation_source == "llm+fallback"
    labels = {node.label for node in response.nodes}
    assert {"LLM-0", "LLM-1"}.issubset(labels)
    assert len(labels & {f"LLM-{index}" for index in range(2, 12)}) == 0


def test_six_eligible_llm_candidates_keep_pure_llm_source() -> None:
    response = _explore_without_memory(
        [_llm_candidate(index, relevance=0.5) for index in range(12)],
        _fallback_pool(),
    )

    assert len(response.nodes) == 6
    assert response.generation_source == "llm"
    assert all(node.label.startswith("LLM-") for node in response.nodes)


def test_fallback_supplement_deduplicates_by_id_and_normalized_label() -> None:
    llm_candidates = [
        _llm_candidate(0, relevance=0.5, label="Shared"),
        *[_llm_candidate(index, relevance=0.10) for index in range(1, 12)],
    ]
    fallback = [
        _fallback_candidate(0, candidate_id="shared", label="Different ID Match"),
        _fallback_candidate(1, candidate_id="different", label=" Shared "),
        _fallback_candidate(2, candidate_id="duplicate-id", label="Duplicate ID"),
        _fallback_candidate(3, candidate_id="duplicate-id", label="Duplicate ID 2"),
        *[_fallback_candidate(index) for index in range(4, 10)],
    ]

    response = _explore_without_memory(llm_candidates, fallback)

    assert len(response.nodes) == 6
    ids = [node.id for node in response.nodes]
    normalized_labels = [node.label.strip().casefold() for node in response.nodes]
    assert len(ids) == len(set(ids))
    assert len(normalized_labels) == len(set(normalized_labels))
    assert "Shared" in {node.label for node in response.nodes}


def test_surprise_level_still_changes_llm_selection() -> None:
    llm_candidates = [
        _llm_candidate(
            index,
            relevance=0.6,
            novelty=min(0.05 + index * 0.08, 1.0),
            cross_domain=min(0.05 + index * 0.08, 1.0),
        )
        for index in range(12)
    ]
    fallback = _fallback_pool()

    low = _explore_without_memory(llm_candidates, fallback, surprise_level=0.2)
    high = _explore_without_memory(llm_candidates, fallback, surprise_level=0.8)

    low_ids = {node.id for node in low.nodes}
    high_ids = {node.id for node in high.nodes}
    assert low_ids != high_ids


def test_memory_agent_path_also_guards_against_empty_selection() -> None:
    service = MagicMock()
    service.get_candidates.return_value = _generation_result(
        [_llm_candidate(index, relevance=0.10) for index in range(12)]
    )
    profile = MemoryProfile(
        anonymous_user_id="guard-user",
        preferred_domains=["测试领域"],
        evidence_count=2,
        memory_signature="guard-signature",
    )

    with patch("app.services.exploration_agent.get_llm_service", return_value=service):
        with patch(
            "app.services.exploration_agent._build_memory_profile_response",
            return_value=(MemoryProfileResponse(available=True, profile=profile), 0.0),
        ):
            with patch(
                "app.services.explore_service._fallback_candidates",
                return_value=_fallback_pool(),
            ):
                response, metrics = run_exploration(
                    ExploreRequest(
                        topic="测试",
                        surprise_level=0.5,
                        anonymous_user_id="guard-user",
                        use_memory=True,
                    )
                )

    assert len(response.nodes) == 6
    assert response.generation_source == "llm+fallback"
    assert response.metadata is not None
    assert response.metadata.memory is not None
    assert response.metadata.memory.available is True
    assert metrics is not None
    assert metrics.exploration_ratio >= 0.0


def test_prompt_contains_short_score_calibration() -> None:
    prompt = _build_prompt("量子计算", 12)

    assert "## Score Calibration" in prompt
    assert "Cross-domain does NOT mean low relevance." in prompt
    assert "0.25 = weak but explainable" in prompt
    assert "A distant candidate may still have relevance >= 0.5" in prompt
    assert "at least 8 candidates have relevance >= 0.30" in prompt
