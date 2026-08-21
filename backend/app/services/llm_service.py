"""LLM Service for Knowledge Wander."""

from __future__ import annotations

import json
import logging
import os
import re
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

from app.models.llm import LLMCandidate, LLMCandidateResponse, LLMConfig

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_ROOT / ".env"
load_dotenv(ENV_FILE, override=False)


def _parse_env_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def _load_llm_config() -> LLMConfig:
    return LLMConfig(
        api_key=os.getenv("LLM_API_KEY") or None,
        base_url=os.getenv("LLM_BASE_URL") or None,
        model=os.getenv("LLM_MODEL") or None,
        timeout_seconds=int(os.getenv("LLM_TIMEOUT_SECONDS", "25")),
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
        candidate_count=int(os.getenv("LLM_CANDIDATE_COUNT", "12")),
        max_tokens=int(os.getenv("LLM_MAX_TOKENS", "3000")),
        json_mode=_parse_env_bool(os.getenv("LLM_JSON_MODE")),
        reasoning_effort=os.getenv("LLM_REASONING_EFFORT", "").strip() or None,
    )


def _resolve_chat_endpoint(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def _candidate_label_id(label: str) -> str:
    normalized = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.casefold()).strip("-")[:48]
    if slug:
        return slug
    digest = __import__("hashlib").sha256(label.encode("utf-8")).hexdigest()[:10]
    return f"candidate-{digest}"


def _normalize_label(value: str) -> str:
    return re.sub(r"[\s\-—]+", " ", value).strip().casefold()


def _deduplicate_candidates(
    candidates: list[LLMCandidate],
) -> list[LLMCandidate]:
    seen: set[str] = set()
    unique: list[LLMCandidate] = []
    for candidate in candidates:
        key = _normalize_label(candidate.label)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _build_prompt(topic: str, candidate_count: int, memory_context: str = "") -> str:
    json_schema = json.dumps(
        {
            "candidates": [
                {
                    "label": "string",
                    "domain": "string",
                    "description": "string",
                    "connection": "string",
                    "relevance": 0.0,
                    "novelty": 0.0,
                    "cross_domain": 0.0,
                }
            ]
        },
        ensure_ascii=False,
    )
    return (
        __import__("app.prompts.knowledge_candidates", fromlist=["KNOWLEDGE_CANDIDATE_PROMPT"])
        .KNOWLEDGE_CANDIDATE_PROMPT.replace("{topic}", topic)
        .replace("{memory_context}", memory_context)
        .replace("{json_schema}", json_schema)
        .replace("{candidate_count}", str(candidate_count))
    )


@dataclass
class LLMGenerationResult:
    candidates: list[LLMCandidate]
    cache_hit: bool
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    latency_ms: float


def _parse_llm_response(raw_text: str) -> list[LLMCandidate]:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        match = re.match(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1)
    parsed = LLMCandidateResponse.model_validate_json(cleaned)
    return _deduplicate_candidates(list(parsed.candidates))


def _extract_usage(data: dict[str, Any]) -> tuple[int | None, int | None, int | None]:
    usage = data.get("usage") or {}
    if not isinstance(usage, dict):
        return None, None, None
    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    total_tokens = usage.get("total_tokens")
    if prompt_tokens is not None:
        prompt_tokens = int(prompt_tokens)
    if completion_tokens is not None:
        completion_tokens = int(completion_tokens)
    if total_tokens is not None:
        total_tokens = int(total_tokens)
    return prompt_tokens, completion_tokens, total_tokens


def _call_llm_with_retry(
    config: LLMConfig,
    prompt: str,
    topic: str,
) -> LLMGenerationResult:
    endpoint = _resolve_chat_endpoint(config.base_url)
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": config.model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a knowledge explorer. "
                    "Always respond with valid JSON only. "
                    "Match all user-facing text to the primary language of the user's topic. "
                    "For Chinese topics, use Simplified Chinese except for necessary proper nouns and acronyms."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
    }
    if config.json_mode:
        payload["response_format"] = {"type": "json_object"}
    if config.reasoning_effort:
        payload["reasoning_effort"] = config.reasoning_effort

    start = time.perf_counter()
    max_attempts = 2
    last_exception: Exception | None = None
    for attempt in range(max_attempts):
        try:
            logger.info("LLM request started: model=%s topic=%s", config.model, topic)
            with httpx.Client(timeout=config.timeout_seconds) as client:
                response = client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                raw_text = data["choices"][0]["message"]["content"]
                candidates = _parse_llm_response(raw_text)
                prompt_tokens, completion_tokens, total_tokens = _extract_usage(data)
                latency_ms = (time.perf_counter() - start) * 1000
                logger.info(
                    "LLM request succeeded: model=%s candidates=%d latency_ms=%.2f",
                    config.model,
                    len(candidates),
                    latency_ms,
                )
                return LLMGenerationResult(
                    candidates=candidates,
                    cache_hit=False,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    latency_ms=latency_ms,
                )
        except Exception as exc:
            last_exception = exc
            if attempt < max_attempts - 1:
                logger.warning("LLM request failed, retrying: %s", exc)
                continue
            raise

    raise last_exception or RuntimeError("LLM request failed")


@dataclass
class CachedCandidatePool:
    result: LLMGenerationResult
    generated_at: float


class LLMService:
    def __init__(self, config: LLMConfig | None = None) -> None:
        self._config = config or _load_llm_config()
        self._cache: dict[str, CachedCandidatePool] = {}
        self._cache_ttl = 900
        self._cache_max_size = 100

    @property
    def config(self) -> LLMConfig:
        """Expose the validated provider configuration to reusable services."""

        return self._config

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        response_format: dict[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Call the configured OpenAI-compatible chat endpoint asynchronously."""

        config = self._config
        if not config.api_key or not config.base_url or not config.model:
            raise RuntimeError("LLM is not configured")

        payload: dict[str, Any] = {
            "model": config.model,
            "messages": messages,
            "temperature": config.temperature if temperature is None else temperature,
            "max_tokens": config.max_tokens if max_tokens is None else max_tokens,
        }
        if tools is not None:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if response_format is not None:
            payload["response_format"] = response_format
        if config.reasoning_effort:
            payload["reasoning_effort"] = config.reasoning_effort

        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
            response = await client.post(
                _resolve_chat_endpoint(config.base_url),
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        if not isinstance(data, dict):
            raise RuntimeError("LLM returned an invalid response")
        logger.info(
            "LLM chat completion succeeded: model=%s latency_ms=%.2f",
            config.model,
            (time.perf_counter() - start) * 1000,
        )
        return data

    def _evict_cache(self) -> None:
        if len(self._cache) <= self._cache_max_size:
            return
        sorted_keys = sorted(self._cache, key=lambda key: self._cache[key].generated_at)
        for key in sorted_keys[: len(self._cache) - self._cache_max_size]:
            del self._cache[key]

    def _cache_key(self, topic: str, memory_signature: str | None = None) -> str:
        signature = memory_signature or "no-memory"
        return f"{_normalize_label(topic)}::{signature}"

    def get_candidates(
        self,
        topic: str,
        memory_context: str = "",
        memory_signature: str | None = None,
    ) -> LLMGenerationResult:
        cache_key = self._cache_key(topic, memory_signature)

        cached = self._cache.get(cache_key)
        if cached and time.time() - cached.generated_at < self._cache_ttl:
            logger.info("LLM cache hit: topic=%s", topic)
            return LLMGenerationResult(
                candidates=list(cached.result.candidates),
                cache_hit=True,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                latency_ms=0.0,
            )

        if not self._config.api_key or not self._config.base_url or not self._config.model:
            raise RuntimeError("LLM is not configured")

        prompt = _build_prompt(topic, self._config.candidate_count, memory_context)
        result = _call_llm_with_retry(self._config, prompt, topic)
        self._cache[cache_key] = CachedCandidatePool(
            result=result,
            generated_at=time.time(),
        )
        self._evict_cache()
        logger.info(
            "LLM cache miss; generated %d candidates for topic=%s",
            len(result.candidates),
            topic,
        )
        return result


_llm_service: LLMService | None = None


def get_llm_service() -> LLMService | None:
    global _llm_service
    config = _load_llm_config()
    if not config.api_key or not config.base_url or not config.model:
        logger.info("LLM not configured; using fallback candidate generation.")
        _llm_service = None
        return None

    if _llm_service is None or _llm_service._config != config:
        _llm_service = LLMService(config=config)
    return _llm_service
