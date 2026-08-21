"""API behavior tests for the Milestone 2+ exploration flow."""

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.models.llm import LLMCandidate
from app.main import app
from app.services.llm_service import LLMGenerationResult


client = TestClient(app)


def _to_generation_result(candidates: list[LLMCandidate]) -> LLMGenerationResult:
    return LLMGenerationResult(
        candidates=candidates,
        cache_hit=False,
        prompt_tokens=None,
        completion_tokens=None,
        total_tokens=None,
        latency_ms=0.0,
    )


@pytest.fixture(autouse=True)
def _disable_real_llm(monkeypatch):
    monkeypatch.setattr(
        "app.services.explore_service.get_llm_service",
        lambda: None,
    )


def test_openapi_docs_are_available() -> None:
    response = client.get("/docs")

    assert response.status_code == 200
    assert "Swagger UI" in response.text


def test_game_development_returns_six_complete_nodes() -> None:
    response = client.post(
        "/api/explore",
        json={"topic": "  游戏开发  ", "surprise_level": 0.5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["root"] == {"id": "game-development", "label": "游戏开发"}
    assert len(payload["nodes"]) == 6
    assert all(
        {
            "id",
            "label",
            "domain",
            "description",
            "connection",
            "surprise_score",
        }
        == set(node)
        for node in payload["nodes"]
    )


def test_unknown_topic_uses_generic_fallback() -> None:
    topic = "量子摄影"
    response = client.post(
        "/api/explore",
        json={"topic": topic, "surprise_level": 0.5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["root"]["label"] == topic
    assert len(payload["nodes"]) == 6
    assert all(topic in node["connection"] for node in payload["nodes"])


def test_empty_topic_is_rejected() -> None:
    response = client.post(
        "/api/explore",
        json={"topic": "   ", "surprise_level": 0.5},
    )

    assert response.status_code == 422


def test_surprise_level_must_be_in_range() -> None:
    for surprise_level in (-0.01, 1.01):
        response = client.post(
            "/api/explore",
            json={"topic": "游戏开发", "surprise_level": surprise_level},
        )

        assert response.status_code == 422


def test_all_surprise_scores_are_within_bounds() -> None:
    response = client.post(
        "/api/explore",
        json={"topic": "游戏开发", "surprise_level": 0.5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert all(0.0 <= node["surprise_score"] <= 1.0 for node in payload["nodes"])


def test_low_and_high_surprise_produce_different_top_six() -> None:
    low_response = client.post(
        "/api/explore",
        json={"topic": "游戏开发", "surprise_level": 0.2},
    )
    high_response = client.post(
        "/api/explore",
        json={"topic": "游戏开发", "surprise_level": 0.8},
    )

    assert low_response.status_code == 200
    assert high_response.status_code == 200

    low_ids = {node["id"] for node in low_response.json()["nodes"]}
    high_ids = {node["id"] for node in high_response.json()["nodes"]}
    assert len(low_ids & high_ids) <= 3


def test_high_surprise_average_is_meaningfully_higher() -> None:
    low_response = client.post(
        "/api/explore",
        json={"topic": "游戏开发", "surprise_level": 0.2},
    )
    high_response = client.post(
        "/api/explore",
        json={"topic": "游戏开发", "surprise_level": 0.8},
    )

    assert low_response.status_code == 200
    assert high_response.status_code == 200

    low_scores = [node["surprise_score"] for node in low_response.json()["nodes"]]
    high_scores = [node["surprise_score"] for node in high_response.json()["nodes"]]

    low_avg = sum(low_scores) / len(low_scores)
    high_avg = sum(high_scores) / len(high_scores)

    assert high_avg > low_avg
    assert high_avg - low_avg >= 0.15


def test_generic_fallback_surprise_affects_results() -> None:
    topic = "量子摄影"
    low_response = client.post(
        "/api/explore",
        json={"topic": topic, "surprise_level": 0.2},
    )
    high_response = client.post(
        "/api/explore",
        json={"topic": topic, "surprise_level": 0.8},
    )

    assert low_response.status_code == 200
    assert high_response.status_code == 200

    low_ids = {node["id"] for node in low_response.json()["nodes"]}
    high_ids = {node["id"] for node in high_response.json()["nodes"]}
    assert len(low_ids & high_ids) <= 3


def test_local_frontend_cors_preflight_is_allowed() -> None:
    response = client.options(
        "/api/explore",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def _mock_llm_candidates():
    return [
        {
            "label": "认知科学",
            "domain": "认知科学",
            "description": "综合心理学与计算理论研究人如何理解世界。",
            "connection": "探索「测试」时需要匹配人的注意、记忆与问题解决方式。",
            "relevance": 0.6,
            "novelty": 0.55,
            "cross_domain": 0.5,
        },
        {
            "label": "建筑空间设计",
            "domain": "建筑学",
            "description": "通过尺度、路径与空间节奏塑造人的行动和感受。",
            "connection": "从「测试」出发，空间组织同样影响人的行动与理解。",
            "relevance": 0.3,
            "novelty": 0.7,
            "cross_domain": 0.7,
        },
        {
            "label": "行为经济学",
            "domain": "经济学",
            "description": "研究真实决策中损失厌恶、锚定效应等非理性行为。",
            "connection": "「测试」中的判断和选择都与真实决策偏差有关。",
            "relevance": 0.35,
            "novelty": 0.65,
            "cross_domain": 0.65,
        },
        {
            "label": "电影镜头语言",
            "domain": "电影学",
            "description": "利用构图、景别、运动和剪辑节奏传递信息与情绪。",
            "connection": "呈现「测试」结果时可以借用镜头语言强化叙事节奏。",
            "relevance": 0.4,
            "novelty": 0.5,
            "cross_domain": 0.45,
        },
        {
            "label": "音乐心理学",
            "domain": "音乐学",
            "description": "探索节奏、音色与和声如何影响注意力、情绪和记忆。",
            "connection": "为「测试」加入声音维度，可以强化情绪与记忆线索。",
            "relevance": 0.25,
            "novelty": 0.6,
            "cross_domain": 0.6,
        },
        {
            "label": "心流理论",
            "domain": "心理学",
            "description": "研究人在挑战与能力平衡时进入高度专注状态的心理体验。",
            "connection": "良好的「测试」设计应帮助人进入并维持心流状态。",
            "relevance": 0.55,
            "novelty": 0.55,
            "cross_domain": 0.5,
        },
        {
            "label": "信息可视化",
            "domain": "信息设计",
            "description": "将数据与抽象关系转化为直观的视觉结构。",
            "connection": "「测试」结果可以通过可视化变得更易理解。",
            "relevance": 0.45,
            "novelty": 0.55,
            "cross_domain": 0.55,
        },
        {
            "label": "系统思维",
            "domain": "复杂系统",
            "description": "从关系、反馈回路与整体结构理解复杂问题。",
            "connection": "把「测试」看作系统，可以发现局部变化如何产生连锁影响。",
            "relevance": 0.5,
            "novelty": 0.5,
            "cross_domain": 0.4,
        },
        {
            "label": "认知偏差",
            "domain": "心理学",
            "description": "研究判断和决策中反复出现的思维捷径与偏差。",
            "connection": "分析「测试」结果时识别认知偏差，可以发现隐藏假设。",
            "relevance": 0.5,
            "novelty": 0.45,
            "cross_domain": 0.45,
        },
        {
            "label": "复杂网络",
            "domain": "网络科学",
            "description": "研究节点与边如何形成小世界、无标度等非随机结构。",
            "connection": "「测试」中的关系往往不是线性的，复杂网络能揭示隐藏模式。",
            "relevance": 0.4,
            "novelty": 0.5,
            "cross_domain": 0.5,
        },
        {
            "label": "视觉叙事",
            "domain": "设计学",
            "description": "借助图像、节奏和信息层级构建可理解的故事。",
            "connection": "视觉叙事能把「测试」中的抽象关系转化为更容易理解的体验。",
            "relevance": 0.4,
            "novelty": 0.5,
            "cross_domain": 0.5,
        },
        {
            "label": "演化心理学",
            "domain": "心理学",
            "description": "从演化压力解释人类认知、情绪与社会行为的起源。",
            "connection": "演化视角可以帮助解释「测试」背后的动机为什么会如此设计。",
            "relevance": 0.35,
            "novelty": 0.55,
            "cross_domain": 0.55,
        },
        {
            "label": "符号学",
            "domain": "符号学",
            "description": "研究符号如何被创造、编码和被不同文化解读。",
            "connection": "「测试」中的术语、图标和仪式都是一种符号，值得解码其意义。",
            "relevance": 0.3,
            "novelty": 0.6,
            "cross_domain": 0.6,
        },
        {
            "label": "文化人类学",
            "domain": "人类学",
            "description": "观察不同群体如何创造意义、习俗与共同身份。",
            "connection": "从文化人类学观察「测试」，可以理解不同群体为何赋予它不同意义。",
            "relevance": 0.35,
            "novelty": 0.6,
            "cross_domain": 0.6,
        },
        {
            "label": "声音景观",
            "domain": "声学",
            "description": "研究环境声音如何塑造场所感、行为和集体记忆。",
            "connection": "为「测试」加入声音维度，可能揭示视觉信息之外的体验线索。",
            "relevance": 0.3,
            "novelty": 0.65,
            "cross_domain": 0.65,
        },
        {
            "label": "仿生设计",
            "domain": "生物学",
            "description": "从自然结构与演化策略中寻找设计和工程启发。",
            "connection": "自然系统可能为「测试」提供意料之外但可验证的结构类比。",
            "relevance": 0.25,
            "novelty": 0.7,
            "cross_domain": 0.7,
        },
        {
            "label": "混沌理论",
            "domain": "数学",
            "description": "研究确定性系统中如何产生对初始条件极度敏感的不可预测行为。",
            "connection": "「测试」中看似随机的结果，可能在混沌视角下显示出隐藏秩序。",
            "relevance": 0.25,
            "novelty": 0.75,
            "cross_domain": 0.75,
        },
        {
            "label": "批判性思维",
            "domain": "哲学",
            "description": "系统地评估证据、识别假设并检验论证结构。",
            "connection": "批判性思维可以帮助你更清晰地审视「测试」中的核心假设。",
            "relevance": 0.4,
            "novelty": 0.4,
            "cross_domain": 0.35,
        },
    ]


def test_llm_success_produces_candidates() -> None:
    mock_service = __import__("unittest.mock").mock.MagicMock()
    mock_service.get_candidates.return_value = _to_generation_result(
        [
            LLMCandidate(**candidate)
            for candidate in _mock_llm_candidates()
        ]
    )

    with patch("app.services.explore_service.get_llm_service", return_value=mock_service):
        response = client.post(
            "/api/explore",
            json={"topic": "测试", "surprise_level": 0.5},
        )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["nodes"]) == 6
    labels = {node["label"] for node in payload["nodes"]}
    assert "认知科学" in labels
    assert "心流理论" in labels


def test_llm_malformed_json_triggers_fallback() -> None:
    mock_service = __import__("unittest.mock").mock.MagicMock()
    mock_service.get_candidates.return_value = _to_generation_result([])

    with patch("app.services.explore_service.get_llm_service", return_value=mock_service):
        response = client.post(
            "/api/explore",
            json={"topic": "测试", "surprise_level": 0.5},
        )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["nodes"]) == 6


def test_llm_http_error_triggers_fallback() -> None:
    mock_service = __import__("unittest.mock").mock.MagicMock()
    mock_service.get_candidates.side_effect = RuntimeError("HTTP 500")

    with patch("app.services.explore_service.get_llm_service", return_value=mock_service):
        response = client.post(
            "/api/explore",
            json={"topic": "测试", "surprise_level": 0.5},
        )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["nodes"]) == 6


def test_missing_api_key_uses_fallback() -> None:
    with patch("app.services.explore_service.get_llm_service", return_value=None):
        response = client.post(
            "/api/explore",
            json={"topic": "测试", "surprise_level": 0.5},
        )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["nodes"]) == 6
    assert all("测试" in node["connection"] for node in payload["nodes"])


def test_llm_duplicate_candidates_deduplicated() -> None:
    from app.services.llm_service import _deduplicate_candidates
    from app.models.llm import LLMCandidate

    raw = [
        LLMCandidate(
            label="认知科学",
            domain="认知科学",
            description="综合心理学与计算理论研究人如何理解世界。",
            connection="探索「测试」时需要匹配人的注意、记忆与问题解决方式。",
            relevance=0.6,
            novelty=0.55,
            cross_domain=0.5,
        ),
        LLMCandidate(
            label="认知科学",
            domain="认知科学",
            description="重复项，应被去重。",
            connection="重复连接。",
            relevance=0.5,
            novelty=0.5,
            cross_domain=0.5,
        ),
        LLMCandidate(
            label="Cognitive Science",
            domain="认知科学",
            description="英文重复项，也应被去重。",
            connection="重复连接。",
            relevance=0.5,
            novelty=0.5,
            cross_domain=0.5,
        ),
    ]

    unique = _deduplicate_candidates(raw)
    labels = [candidate.label for candidate in unique]
    assert labels.count("认知科学") == 1


def test_llm_insufficient_candidates_supplemented_with_fallback() -> None:
    mock_service = __import__("unittest.mock").mock.MagicMock()
    mock_service.get_candidates.return_value = _to_generation_result(
        [
            LLMCandidate(
                label="认知科学",
                domain="认知科学",
                description="综合心理学与计算理论研究人如何理解世界。",
                connection="探索「测试」时需要匹配人的注意、记忆与问题解决方式。",
                relevance=0.6,
                novelty=0.55,
                cross_domain=0.5,
            ),
        ]
    )

    with patch("app.services.explore_service.get_llm_service", return_value=mock_service):
        response = client.post(
            "/api/explore",
            json={"topic": "测试", "surprise_level": 0.5},
        )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["nodes"]) == 6


def test_llm_cache_avoids_duplicate_calls_for_same_topic() -> None:
    from app.models.llm import LLMConfig, LLMCandidate
    from app.services.llm_service import LLMService

    service = LLMService(
        config=LLMConfig(
            api_key="test-key",
            base_url="http://localhost:8080/v1",
            model="test-model",
        )
    )

    with patch("app.services.llm_service._call_llm_with_retry") as mock_call:
        mock_call.return_value = LLMGenerationResult(
            candidates=[
                LLMCandidate(
                    label="认知科学",
                    domain="认知科学",
                    description="综合心理学与计算理论研究人如何理解世界。",
                    connection="探索「测试」时需要匹配人的注意、记忆与问题解决方式。",
                    relevance=0.6,
                    novelty=0.55,
                    cross_domain=0.5,
                ),
            ],
            cache_hit=False,
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            latency_ms=1.0,
        )
        service.get_candidates("缓存测试")
        service.get_candidates("缓存测试")

    assert mock_call.call_count == 1


def test_llm_prompt_includes_language_rules_for_chinese_topic() -> None:
    from app.services.llm_service import _build_prompt

    prompt = _build_prompt("游戏开发", 18)
    assert "Simplified Chinese" in prompt
    assert "user-facing" in prompt
    assert "proper noun" in prompt


def test_llm_sixteen_candidates_uses_llm_only() -> None:
    from app.services.explore_service import explore_topic
    from app.models.explore import ExploreRequest

    mock_service = __import__("unittest.mock").mock.MagicMock()
    mock_service.get_candidates.return_value = _to_generation_result(
        [
            LLMCandidate(
                label=f"LLM-{i}",
                domain="测试",
                description="desc",
                connection="conn",
                relevance=0.5,
                novelty=0.5,
                cross_domain=0.5,
            )
            for i in range(16)
        ]
    )

    with patch("app.services.explore_service.get_llm_service", return_value=mock_service):
        response = explore_topic(ExploreRequest(topic="测试", surprise_level=0.5))

    labels = {node.label for node in response.nodes}
    assert all(label.startswith("LLM-") for label in labels)
    assert response.generation_source == "llm"


def test_llm_success_top_six_all_from_llm() -> None:
    mock_service = __import__("unittest.mock").mock.MagicMock()
    mock_service.get_candidates.return_value = _to_generation_result(
        [
            LLMCandidate(
                label=f"LLM-{i}",
                domain="测试",
                description="desc",
                connection="conn",
                relevance=0.5,
                novelty=0.5,
                cross_domain=0.5,
            )
            for i in range(16)
        ]
    )

    with patch("app.services.explore_service.get_llm_service", return_value=mock_service):
        response = client.post(
            "/api/explore",
            json={"topic": "测试", "surprise_level": 0.5},
        )

    assert response.status_code == 200
    payload = response.json()
    labels = {node["label"] for node in payload["nodes"]}
    assert all(label.startswith("LLM-") for label in labels)
    assert payload["generation_source"] == "llm"


def test_llm_ten_candidates_supplements_two_fallback() -> None:
    mock_service = __import__("unittest.mock").mock.MagicMock()
    mock_service.get_candidates.return_value = _to_generation_result(
        [
            LLMCandidate(
                label=f"LLM-{i}",
                domain="测试",
                description="desc",
                connection="conn",
                relevance=0.5,
                novelty=0.5,
                cross_domain=0.5,
            )
            for i in range(10)
        ]
    )

    with patch("app.services.explore_service.get_llm_service", return_value=mock_service):
        response = client.post(
            "/api/explore",
            json={"topic": "测试", "surprise_level": 0.5},
        )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["nodes"]) == 6
    assert payload["generation_source"] == "llm+fallback"
    llm_labels = {f"LLM-{i}" for i in range(10)}
    node_labels = {node["label"] for node in payload["nodes"]}
    assert len(node_labels & llm_labels) >= 4


def test_llm_fewer_than_six_candidates_uses_full_fallback() -> None:
    mock_service = __import__("unittest.mock").mock.MagicMock()
    mock_service.get_candidates.return_value = _to_generation_result(
        [
            LLMCandidate(
                label="认知科学",
                domain="认知科学",
                description="desc",
                connection="conn",
                relevance=0.5,
                novelty=0.5,
                cross_domain=0.5,
            ),
        ]
    )

    with patch("app.services.explore_service.get_llm_service", return_value=mock_service):
        response = client.post(
            "/api/explore",
            json={"topic": "测试", "surprise_level": 0.5},
        )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["nodes"]) == 6
    assert payload["generation_source"] == "fallback"


def test_llm_request_failure_uses_fallback() -> None:
    mock_service = __import__("unittest.mock").mock.MagicMock()
    mock_service.get_candidates.side_effect = RuntimeError("HTTP 500")

    with patch("app.services.explore_service.get_llm_service", return_value=mock_service):
        response = client.post(
            "/api/explore",
            json={"topic": "测试", "surprise_level": 0.5},
        )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["nodes"]) == 6
    assert payload["generation_source"] == "fallback"


def test_generation_source_llm() -> None:
    mock_service = __import__("unittest.mock").mock.MagicMock()
    mock_service.get_candidates.return_value = _to_generation_result(
        [
            LLMCandidate(
                label=f"LLM-{i}",
                domain="测试",
                description="desc",
                connection="conn",
                relevance=0.5,
                novelty=0.5,
                cross_domain=0.5,
            )
            for i in range(16)
        ]
    )

    with patch("app.services.explore_service.get_llm_service", return_value=mock_service):
        response = client.post(
            "/api/explore",
            json={"topic": "测试", "surprise_level": 0.5},
        )

    assert response.status_code == 200
    assert response.json()["generation_source"] == "llm"


def test_generation_source_llm_plus_fallback() -> None:
    mock_service = __import__("unittest.mock").mock.MagicMock()
    mock_service.get_candidates.return_value = _to_generation_result(
        [
            LLMCandidate(
                label=f"LLM-{i}",
                domain="测试",
                description="desc",
                connection="conn",
                relevance=0.5,
                novelty=0.5,
                cross_domain=0.5,
            )
            for i in range(10)
        ]
    )

    with patch("app.services.explore_service.get_llm_service", return_value=mock_service):
        response = client.post(
            "/api/explore",
            json={"topic": "测试", "surprise_level": 0.5},
        )

    assert response.status_code == 200
    assert response.json()["generation_source"] == "llm+fallback"


def test_generation_source_fallback() -> None:
    with patch("app.services.explore_service.get_llm_service", return_value=None):
        response = client.post(
            "/api/explore",
            json={"topic": "测试", "surprise_level": 0.5},
        )

    assert response.status_code == 200
    assert response.json()["generation_source"] == "fallback"


def test_same_topic_different_surprise_uses_cached_llm_pool() -> None:
    from app.services.llm_service import LLMService, _call_llm_with_retry
    from app.models.llm import LLMConfig
    from app.services.explore_service import explore_topic
    from app.models.explore import ExploreRequest

    service = LLMService(
        config=LLMConfig(
            api_key="test-key",
            base_url="http://localhost:8080/v1",
            model="test-model",
        )
    )

    candidates = [
        LLMCandidate(
            label=f"Candidate-{i}",
            domain="测试",
            description="desc",
            connection="conn",
            relevance=0.5,
            novelty=min(0.3 + i * 0.05, 1.0),
            cross_domain=0.5,
        )
        for i in range(16)
    ]

    with patch(
        "app.services.llm_service._call_llm_with_retry",
        return_value=LLMGenerationResult(
            candidates=candidates,
            cache_hit=False,
            prompt_tokens=100,
            completion_tokens=200,
            total_tokens=300,
            latency_ms=1.5,
        ),
    ) as mock_call:
        with patch(
            "app.services.explore_service.get_llm_service",
            return_value=service,
        ):
            low = explore_topic(ExploreRequest(topic="摄影史", surprise_level=0.2))
            high = explore_topic(ExploreRequest(topic="摄影史", surprise_level=0.8))

    assert mock_call.call_count == 1
    low_ids = {node.id for node in low.nodes}
    high_ids = {node.id for node in high.nodes}
    assert len(low_ids & high_ids) <= 3

    low_avg = sum(node.surprise_score for node in low.nodes) / len(low.nodes)
    high_avg = sum(node.surprise_score for node in high.nodes) / len(high.nodes)
    assert high_avg > low_avg


def test_llm_prompt_no_memory_placeholder_removed() -> None:
    from app.services.llm_service import _build_prompt

    prompt = _build_prompt("摄影史", 18, "")
    assert "摄影史" in prompt
    assert "{memory_context}" not in prompt
    assert "## User Memory" not in prompt


def test_llm_prompt_with_memory_single_insertion() -> None:
    from app.services.llm_service import _build_prompt

    memory_block = "## User Memory\nPreferred domains:\n- 心理学"
    prompt = _build_prompt("摄影史", 18, memory_block)
    assert prompt.count("## User Memory") == 1
    assert "心理学" in prompt
    assert prompt.count("心理学") == 1


def test_cache_miss_then_hit_with_different_surprise() -> None:
    from app.services.llm_service import LLMService, _call_llm_with_retry
    from app.models.llm import LLMConfig
    from app.services.explore_service import explore_topic
    from app.models.explore import ExploreRequest

    service = LLMService(
        config=LLMConfig(
            api_key="test-key",
            base_url="http://localhost:8080/v1",
            model="test-model",
        )
    )

    candidates = [
        LLMCandidate(
            label=f"Candidate-{i}",
            domain="测试",
            description="desc",
            connection="conn",
            relevance=0.5,
            novelty=min(0.3 + i * 0.05, 1.0),
            cross_domain=0.5,
        )
        for i in range(16)
    ]

    with patch(
        "app.services.llm_service._call_llm_with_retry",
        return_value=LLMGenerationResult(
            candidates=candidates,
            cache_hit=False,
            prompt_tokens=100,
            completion_tokens=200,
            total_tokens=300,
            latency_ms=1.5,
        ),
    ) as mock_call:
        with patch(
            "app.services.explore_service.get_llm_service",
            return_value=service,
        ):
            first = explore_topic(ExploreRequest(topic="摄影史", surprise_level=0.2))
            second = explore_topic(ExploreRequest(topic="摄影史", surprise_level=0.8))

    assert mock_call.call_count == 1
    assert first.metadata is not None
    assert second.metadata is not None
    assert first.metadata.agent_metrics is not None
    assert second.metadata.agent_metrics is not None
    assert first.metadata.agent_metrics.candidate_cache_hit is False
    assert second.metadata.agent_metrics.candidate_cache_hit is True
    assert second.metadata.agent_metrics.prompt_tokens == 0
    assert second.metadata.agent_metrics.completion_tokens == 0
    assert second.metadata.agent_metrics.total_tokens == 0


def test_provider_usage_metrics_propagated_to_metadata() -> None:
    from app.services.llm_service import LLMService, _call_llm_with_retry
    from app.models.llm import LLMConfig
    from app.services.explore_service import explore_topic
    from app.models.explore import ExploreRequest

    service = LLMService(
        config=LLMConfig(
            api_key="test-key",
            base_url="http://localhost:8080/v1",
            model="test-model",
        )
    )

    candidates = [
        LLMCandidate(
            label=f"Candidate-{i}",
            domain="测试",
            description="desc",
            connection="conn",
            relevance=0.5,
            novelty=0.5,
            cross_domain=0.5,
        )
        for i in range(16)
    ]

    with patch(
        "app.services.llm_service._call_llm_with_retry",
        return_value=LLMGenerationResult(
            candidates=candidates,
            cache_hit=False,
            prompt_tokens=123,
            completion_tokens=456,
            total_tokens=579,
            latency_ms=1.8,
        ),
    ):
        with patch(
            "app.services.explore_service.get_llm_service",
            return_value=service,
        ):
            response = explore_topic(ExploreRequest(topic="摄影史", surprise_level=0.5))

    assert response.metadata is not None
    assert response.metadata.agent_metrics is not None
    assert response.metadata.agent_metrics.prompt_tokens == 123
    assert response.metadata.agent_metrics.completion_tokens == 456
    assert response.metadata.agent_metrics.total_tokens == 579
    assert response.metadata.agent_metrics.candidate_cache_hit is False


def test_provider_without_usage_metrics_returns_none() -> None:
    from app.services.llm_service import LLMService, _call_llm_with_retry
    from app.models.llm import LLMConfig
    from app.services.explore_service import explore_topic
    from app.models.explore import ExploreRequest

    service = LLMService(
        config=LLMConfig(
            api_key="test-key",
            base_url="http://localhost:8080/v1",
            model="test-model",
        )
    )

    candidates = [
        LLMCandidate(
            label=f"Candidate-{i}",
            domain="测试",
            description="desc",
            connection="conn",
            relevance=0.5,
            novelty=0.5,
            cross_domain=0.5,
        )
        for i in range(16)
    ]

    with patch(
        "app.services.llm_service._call_llm_with_retry",
        return_value=LLMGenerationResult(
            candidates=candidates,
            cache_hit=False,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            latency_ms=1.0,
        ),
    ):
        with patch(
            "app.services.explore_service.get_llm_service",
            return_value=service,
        ):
            response = explore_topic(ExploreRequest(topic="摄影史", surprise_level=0.5))

    assert response.metadata is not None
    assert response.metadata.agent_metrics is not None
    assert response.metadata.agent_metrics.prompt_tokens is None
    assert response.metadata.agent_metrics.completion_tokens is None
    assert response.metadata.agent_metrics.total_tokens is None


def test_memory_cache_isolation_different_signature() -> None:
    from app.services.llm_service import LLMService, _call_llm_with_retry
    from app.models.llm import LLMConfig
    from app.services.explore_service import explore_topic
    from app.models.explore import ExploreRequest
    from app.models.memory import MemoryProfile

    service = LLMService(
        config=LLMConfig(
            api_key="test-key",
            base_url="http://localhost:8080/v1",
            model="test-model",
        )
    )

    candidates_a = [
        LLMCandidate(
            label=f"A-{i}",
            domain="测试",
            description="desc",
            connection="conn",
            relevance=0.5,
            novelty=0.5,
            cross_domain=0.5,
        )
        for i in range(16)
    ]
    candidates_b = [
        LLMCandidate(
            label=f"B-{i}",
            domain="测试",
            description="desc",
            connection="conn",
            relevance=0.5,
            novelty=0.5,
            cross_domain=0.5,
        )
        for i in range(16)
    ]

    call_count = 0

    def fake_call(config, prompt, topic):
        nonlocal call_count
        call_count += 1
        return LLMGenerationResult(
            candidates=candidates_a if call_count == 1 else candidates_b,
            cache_hit=False,
            prompt_tokens=100,
            completion_tokens=200,
            total_tokens=300,
            latency_ms=1.0,
        )

    profile_a = MemoryProfile(
        anonymous_user_id="user-a",
        preferred_domains=[],
        disliked_domains=[],
        liked_concepts=[],
        disliked_concepts=[],
        preferred_surprise_level=0.5,
        evidence_count=2,
        updated_at="2024-01-01T00:00:00+00:00",
        memory_signature="sig-a",
    )
    profile_b = MemoryProfile(
        anonymous_user_id="user-b",
        preferred_domains=[],
        disliked_domains=[],
        liked_concepts=[],
        disliked_concepts=[],
        preferred_surprise_level=0.5,
        evidence_count=2,
        updated_at="2024-01-01T00:00:00+00:00",
        memory_signature="sig-b",
    )

    with patch(
        "app.services.llm_service._call_llm_with_retry",
        side_effect=fake_call,
    ):
        with patch(
            "app.services.explore_service.get_llm_service",
            return_value=service,
        ):
            with patch(
                "app.services.exploration_agent.get_memory",
                side_effect=[profile_a, profile_b],
            ):
                explore_topic(ExploreRequest(topic="摄影史", surprise_level=0.5, anonymous_user_id="user-a", use_memory=True))
                explore_topic(ExploreRequest(topic="摄影史", surprise_level=0.5, anonymous_user_id="user-b", use_memory=True))

    assert call_count == 2


def test_memory_off_uses_no_memory_cache_namespace() -> None:
    from app.services.llm_service import LLMService, _call_llm_with_retry
    from app.models.llm import LLMConfig
    from app.services.explore_service import explore_topic
    from app.models.explore import ExploreRequest
    from app.models.memory import MemoryProfile

    service = LLMService(
        config=LLMConfig(
            api_key="test-key",
            base_url="http://localhost:8080/v1",
            model="test-model",
        )
    )

    candidates = [
        LLMCandidate(
            label=f"Candidate-{i}",
            domain="测试",
            description="desc",
            connection="conn",
            relevance=0.5,
            novelty=0.5,
            cross_domain=0.5,
        )
        for i in range(16)
    ]

    call_count = 0

    def fake_call(config, prompt, topic):
        nonlocal call_count
        call_count += 1
        return LLMGenerationResult(
            candidates=candidates,
            cache_hit=False,
            prompt_tokens=100,
            completion_tokens=200,
            total_tokens=300,
            latency_ms=1.0,
        )

    profile_with_memory = MemoryProfile(
        anonymous_user_id="user-a",
        preferred_domains=["心理学"],
        disliked_domains=[],
        liked_concepts=[],
        disliked_concepts=[],
        preferred_surprise_level=0.5,
        evidence_count=2,
        updated_at="2024-01-01T00:00:00+00:00",
        memory_signature="sig-a",
    )

    with patch(
        "app.services.llm_service._call_llm_with_retry",
        side_effect=fake_call,
    ):
        with patch(
            "app.services.explore_service.get_llm_service",
            return_value=service,
        ):
            with patch(
                "app.services.exploration_agent.get_memory",
                return_value=profile_with_memory,
            ):
                explore_topic(ExploreRequest(topic="摄影史", surprise_level=0.5, anonymous_user_id="user-a", use_memory=True))
                explore_topic(ExploreRequest(topic="摄影史", surprise_level=0.5, use_memory=False))

    assert call_count == 2
