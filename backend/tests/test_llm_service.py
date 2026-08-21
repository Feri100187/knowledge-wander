"""Focused tests for LLM generation configuration and request payloads."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from app.models.llm import LLMConfig
from app.services.llm_service import (
    _build_prompt,
    _call_llm_with_retry,
    _load_llm_config,
)


def _provider_response(candidate_count: int = 8) -> MagicMock:
    candidates = [
        {
            "label": f"方向 {index}",
            "domain": "测试领域",
            "description": "一句简短描述。",
            "connection": "一句具体连接。",
            "relevance": 0.5,
            "novelty": 0.5,
            "cross_domain": 0.5,
        }
        for index in range(candidate_count)
    ]
    response = MagicMock()
    response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({"candidates": candidates}, ensure_ascii=False)
                }
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
        },
    }
    return response


def test_default_llm_config_uses_optimized_generation_defaults(monkeypatch) -> None:
    monkeypatch.delenv("LLM_CANDIDATE_COUNT", raising=False)
    monkeypatch.delenv("LLM_MAX_TOKENS", raising=False)
    monkeypatch.delenv("LLM_JSON_MODE", raising=False)
    monkeypatch.delenv("LLM_REASONING_EFFORT", raising=False)

    config = _load_llm_config()

    assert config.candidate_count == 12
    assert config.max_tokens == 3000
    assert config.json_mode is False
    assert config.reasoning_effort is None


def test_prompt_uses_llm_candidate_count_12(monkeypatch) -> None:
    monkeypatch.setenv("LLM_CANDIDATE_COUNT", "12")
    config = _load_llm_config()
    prompt = _build_prompt("摄影史", config.candidate_count)

    assert "Generate exactly 12 candidates." in prompt
    assert "between 16 and 18" not in prompt
    assert "{candidate_count}" not in prompt


@pytest.mark.parametrize("candidate_count", [8, 12, 18])
def test_prompt_supports_configured_candidate_counts(candidate_count: int) -> None:
    prompt = _build_prompt("人工智能", candidate_count)

    assert f"Generate exactly {candidate_count} candidates." in prompt
    assert "between 16 and 18" not in prompt


def test_prompt_requests_concise_candidate_text() -> None:
    prompt = _build_prompt("游戏开发", 12)

    assert "Keep each description concise: one short sentence." in prompt
    assert "Keep each connection concise: one short sentence." in prompt
    assert "description <= 40 Chinese characters" in prompt
    assert "connection <= 60 Chinese characters" in prompt


def _capture_payload(config: LLMConfig) -> dict[str, object]:
    client = MagicMock()
    client.__enter__.return_value = client
    client.post.return_value = _provider_response()
    prompt = _build_prompt("测试", config.candidate_count)

    with patch("app.services.llm_service.httpx.Client", return_value=client):
        _call_llm_with_retry(config, prompt, "测试")

    return client.post.call_args.kwargs["json"]


@pytest.mark.parametrize("json_mode", [False, True])
def test_payload_uses_max_tokens_and_optional_json_mode(json_mode: bool) -> None:
    config = LLMConfig(
        api_key="test-key",
        base_url="http://localhost:8080/v1",
        model="test-model",
        max_tokens=3000,
        json_mode=json_mode,
    )
    payload = _capture_payload(config)
    assert payload["max_tokens"] == 3000
    assert "reasoning_effort" not in payload
    if json_mode:
        assert payload["response_format"] == {"type": "json_object"}
    else:
        assert "response_format" not in payload


@pytest.mark.parametrize("reasoning_effort", ["low", "medium", "high"])
def test_load_and_send_configured_reasoning_effort(
    monkeypatch,
    reasoning_effort: str,
) -> None:
    monkeypatch.setenv("LLM_REASONING_EFFORT", reasoning_effort)
    config = _load_llm_config()

    assert config.reasoning_effort == reasoning_effort
    payload = _capture_payload(
        LLMConfig(
            api_key="test-key",
            base_url="http://localhost:8080/v1",
            model="test-model",
            reasoning_effort=config.reasoning_effort,
        )
    )
    assert payload["reasoning_effort"] == reasoning_effort


@pytest.mark.parametrize("raw_value", ["", "   "])
def test_empty_reasoning_effort_is_not_sent(monkeypatch, raw_value: str) -> None:
    monkeypatch.setenv("LLM_REASONING_EFFORT", raw_value)

    config = _load_llm_config()

    assert config.reasoning_effort is None
    payload = _capture_payload(
        LLMConfig(
            api_key="test-key",
            base_url="http://localhost:8080/v1",
            model="test-model",
        )
    )
    assert "reasoning_effort" not in payload


def test_invalid_reasoning_effort_fails_configuration_validation(monkeypatch) -> None:
    monkeypatch.setenv("LLM_REASONING_EFFORT", "ultra")

    with pytest.raises(ValidationError):
        _load_llm_config()


def test_json_mode_and_reasoning_effort_are_sent_together() -> None:
    payload = _capture_payload(
        LLMConfig(
            api_key="test-key",
            base_url="http://localhost:8080/v1",
            model="test-model",
            json_mode=True,
            reasoning_effort="low",
        )
    )

    assert payload["response_format"] == {"type": "json_object"}
    assert payload["reasoning_effort"] == "low"
