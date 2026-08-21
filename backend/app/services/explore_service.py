"""Explore service backed by the Surprise Engine and optional LLM."""

from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import List

from app.models.explore import (
    ExploreNode,
    ExploreRequest,
    ExploreResponse,
    ExploreResponseMetadata,
    ExploreRoot,
)
from app.models.llm import LLMCandidate
from app.models.memory import MemoryProfileResponse
from app.services.exploration_agent import run_exploration
from app.services.llm_service import (
    _candidate_label_id,
    _normalize_label,
    get_llm_service,
)
from app.services.surprise_engine import (
    Candidate,
    select_top_candidates,
    to_explore_nodes,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GenericCandidateTemplate:
    id: str
    label: str
    domain: str
    description: str
    connection: str
    relevance: float
    novelty: float
    cross_domain: float


GAME_DEVELOPMENT_CANDIDATES = [
    Candidate(
        id="game-design",
        label="游戏设计",
        domain="设计学",
        description="研究规则、机制与体验如何共同构成好玩的游戏系统。",
        connection="游戏开发的核心目标就是创造可玩的体验，游戏设计直接定义了这个目标本身。",
        relevance=0.9,
        novelty=0.2,
        cross_domain=0.1,
    ),
    Candidate(
        id="computer-graphics",
        label="计算机图形学",
        domain="计算机科学",
        description="研究如何用算法生成、渲染和操作视觉内容。",
        connection="游戏中的角色、场景和特效都依赖图形学算法实时渲染。",
        relevance=0.85,
        novelty=0.25,
        cross_domain=0.15,
    ),
    Candidate(
        id="hci",
        label="人机交互",
        domain="交互设计",
        description="研究人与系统之间如何高效、愉悦地交换信息与意图。",
        connection="手柄、界面和交互逻辑都需要匹配玩家的感知与操作习惯。",
        relevance=0.6,
        novelty=0.3,
        cross_domain=0.2,
    ),
    Candidate(
        id="interaction-design",
        label="交互设计",
        domain="设计学",
        description="规划产品如何响应用户操作，塑造可理解的行为映射。",
        connection="从菜单导航到技能释放，交互设计决定游戏能否被轻松上手。",
        relevance=0.6,
        novelty=0.3,
        cross_domain=0.25,
    ),
    Candidate(
        id="narrative-design",
        label="叙事设计",
        domain="叙事学",
        description="通过任务、对白和环境细节构建连贯且有意义的游戏故事。",
        connection="即使是最休闲的游戏，也需要叙事锚点让玩家产生情感投入。",
        relevance=0.7,
        novelty=0.35,
        cross_domain=0.25,
    ),
    Candidate(
        id="unity-engine",
        label="Unity 引擎",
        domain="工程工具",
        description="一个跨平台实时开发平台，广泛用于游戏和交互体验构建。",
        connection="许多独立和商业游戏都直接在 Unity 中实现玩法、逻辑和发布。",
        relevance=0.9,
        novelty=0.1,
        cross_domain=0.05,
    ),
    Candidate(
        id="procedural-generation",
        label="程序化生成",
        domain="算法",
        description="用规则和随机算法自动创建内容，而非完全手工制作。",
        connection="程序化地图、任务和配乐可以大幅扩展游戏的可重复游玩性。",
        relevance=0.6,
        novelty=0.4,
        cross_domain=0.3,
    ),
    Candidate(
        id="user-psychology",
        label="用户心理学",
        domain="心理学",
        description="研究用户如何感知、学习和形成使用习惯。",
        connection="新手引导、界面反馈和长期留存都建立在对玩家心理的理解上。",
        relevance=0.5,
        novelty=0.5,
        cross_domain=0.5,
    ),
    Candidate(
        id="cinematic-language",
        label="电影镜头语言",
        domain="电影学",
        description="利用构图、景别、运动和剪辑节奏传递信息与情绪。",
        connection="游戏镜头与过场叙事借用电影语言，同时还要回应玩家的实时控制。",
        relevance=0.45,
        novelty=0.5,
        cross_domain=0.45,
    ),
    Candidate(
        id="music-psychology",
        label="音乐心理学",
        domain="音乐学",
        description="探索节奏、音色与和声如何影响注意力、情绪和记忆。",
        connection="动态配乐和声音反馈能够强化游戏节奏，并帮助玩家形成情绪记忆。",
        relevance=0.3,
        novelty=0.6,
        cross_domain=0.6,
    ),
    Candidate(
        id="cognitive-science",
        label="认知科学",
        domain="认知科学",
        description="综合心理学、神经科学与计算理论研究人如何理解世界。",
        connection="教程、界面和谜题都需要匹配玩家的注意、记忆与问题解决方式。",
        relevance=0.5,
        novelty=0.5,
        cross_domain=0.45,
    ),
    Candidate(
        id="flow-theory",
        label="心流理论",
        domain="心理学",
        description="研究人在挑战与能力平衡时进入高度专注状态的心理体验。",
        connection="游戏难度曲线与即时反馈会直接影响玩家能否进入并维持心流状态。",
        relevance=0.55,
        novelty=0.55,
        cross_domain=0.5,
    ),
    Candidate(
        id="architectural-space",
        label="建筑空间设计",
        domain="建筑学",
        description="通过尺度、路径、视线与空间节奏塑造人的行动和感受。",
        connection="关卡设计同样需要组织动线、空间层次和视觉引导，让玩家自然理解环境。",
        relevance=0.35,
        novelty=0.7,
        cross_domain=0.7,
    ),
    Candidate(
        id="behavioral-economics",
        label="行为经济学",
        domain="经济学",
        description="研究真实决策中损失厌恶、锚定效应等非理性行为。",
        connection="游戏内奖励、资源取舍和付费设计都与玩家如何感知收益和损失有关。",
        relevance=0.3,
        novelty=0.65,
        cross_domain=0.65,
    ),
    Candidate(
        id="sound-design",
        label="声音设计",
        domain="声学",
        description="用环境音、 Foley 和合成音色构建空间感与情绪信号。",
        connection="脚步声、武器音效和背景音共同告诉玩家“你在哪里、发生了什么”。",
        relevance=0.5,
        novelty=0.45,
        cross_domain=0.4,
    ),
    Candidate(
        id="environmental-psychology",
        label="环境心理学",
        domain="心理学",
        description="研究物理环境如何影响情绪、行为与认知负荷。",
        connection="不同的关卡氛围——幽闭、开阔、明亮——都会改变玩家的紧张与放松程度。",
        relevance=0.25,
        novelty=0.6,
        cross_domain=0.65,
    ),
    Candidate(
        id="sociology",
        label="社会学",
        domain="社会学",
        description="研究群体互动、规范形成和社会结构如何影响个体行为。",
        connection="多人游戏中的公会、匹配机制和社区文化都可以用社会学视角理解。",
        relevance=0.25,
        novelty=0.7,
        cross_domain=0.7,
    ),
    Candidate(
        id="infographics",
        label="信息可视化",
        domain="信息设计",
        description="将数据与抽象关系转化为直观的视觉结构，帮助快速理解。",
        connection="游戏中的 HUD、技能树和数据面板都是信息可视化在交互场景下的应用。",
        relevance=0.3,
        novelty=0.55,
        cross_domain=0.55,
    ),
]


GENERIC_TEMPLATES = [
    GenericCandidateTemplate(
        id="game-design",
        label="游戏化设计",
        domain="设计学",
        description="将游戏机制迁移到非游戏场景，以提升参与度和动机。",
        connection="如果「{topic}」需要提升参与度，可以参考游戏化设计中的奖励与进度机制。",
        relevance=0.45,
        novelty=0.35,
        cross_domain=0.3,
    ),
    GenericCandidateTemplate(
        id="critical-thinking",
        label="批判性思维",
        domain="哲学",
        description="系统地评估证据、识别假设并检验论证结构。",
        connection="批判性思维可以帮助你更清晰地审视「{topic}」中的核心假设。",
        relevance=0.4,
        novelty=0.4,
        cross_domain=0.35,
    ),
    GenericCandidateTemplate(
        id="information-theory",
        label="信息论",
        domain="数学",
        description="研究信息的量化、传输与压缩，以及噪声对信号的影响。",
        connection="信息论为「{topic}」中的不确定性、编码与沟通提供了精确框架。",
        relevance=0.45,
        novelty=0.4,
        cross_domain=0.35,
    ),
    GenericCandidateTemplate(
        id="systems-thinking",
        label="系统思维",
        domain="复杂系统",
        description="从关系、反馈回路与整体结构理解复杂问题。",
        connection="把「{topic}」看作一个系统，可以发现局部变化如何产生连锁影响。",
        relevance=0.45,
        novelty=0.5,
        cross_domain=0.4,
    ),
    GenericCandidateTemplate(
        id="cognitive-biases",
        label="认知偏差",
        domain="心理学",
        description="研究判断和决策中反复出现的思维捷径与偏差。",
        connection="探索「{topic}」时识别认知偏差，有助于发现被直觉忽略的假设。",
        relevance=0.5,
        novelty=0.45,
        cross_domain=0.45,
    ),
    GenericCandidateTemplate(
        id="complex-networks",
        label="复杂网络",
        domain="网络科学",
        description="研究节点与边如何形成小世界、无标度等非随机结构。",
        connection="「{topic}」中的关系往往不是线性的，复杂网络能揭示隐藏的连接模式。",
        relevance=0.4,
        novelty=0.5,
        cross_domain=0.5,
    ),
    GenericCandidateTemplate(
        id="visual-storytelling",
        label="视觉叙事",
        domain="设计学",
        description="借助图像、节奏和信息层级构建可理解的故事。",
        connection="视觉叙事能把「{topic}」中的抽象关系转化为更容易理解的体验。",
        relevance=0.4,
        novelty=0.5,
        cross_domain=0.5,
    ),
    GenericCandidateTemplate(
        id="evolutionary-psychology",
        label="演化心理学",
        domain="心理学",
        description="从演化压力解释人类认知、情绪与社会行为的起源。",
        connection="演化视角可以帮助解释「{topic}」背后的动机为什么会如此设计。",
        relevance=0.35,
        novelty=0.55,
        cross_domain=0.55,
    ),
    GenericCandidateTemplate(
        id="semiotics",
        label="符号学",
        domain="符号学",
        description="研究符号如何被创造、编码和被不同文化解读。",
        connection="「{topic}」中的术语、图标和仪式都是一种符号，值得解码其意义。",
        relevance=0.3,
        novelty=0.6,
        cross_domain=0.6,
    ),
    GenericCandidateTemplate(
        id="cultural-anthropology",
        label="文化人类学",
        domain="人类学",
        description="观察不同群体如何创造意义、习俗与共同身份。",
        connection="从文化人类学观察「{topic}」，可以理解不同群体为何赋予它不同意义。",
        relevance=0.35,
        novelty=0.6,
        cross_domain=0.6,
    ),
    GenericCandidateTemplate(
        id="soundscape-studies",
        label="声音景观",
        domain="声学",
        description="研究环境声音如何塑造场所感、行为和集体记忆。",
        connection="为「{topic}」加入声音维度，可能揭示视觉信息之外的体验线索。",
        relevance=0.3,
        novelty=0.65,
        cross_domain=0.65,
    ),
    GenericCandidateTemplate(
        id="biomimicry",
        label="仿生设计",
        domain="生物学",
        description="从自然结构与演化策略中寻找设计和工程启发。",
        connection="自然系统可能为「{topic}」提供意料之外但可验证的结构类比。",
        relevance=0.25,
        novelty=0.7,
        cross_domain=0.7,
    ),
    GenericCandidateTemplate(
        id="chaos-theory",
        label="混沌理论",
        domain="数学",
        description="研究确定性系统中如何产生对初始条件极度敏感的不可预测行为。",
        connection="「{topic}」中看似随机的结果，可能在混沌视角下显示出隐藏秩序。",
        relevance=0.25,
        novelty=0.75,
        cross_domain=0.75,
    ),
]


def _topic_id(topic: str) -> str:
    if topic.casefold() in {"游戏开发", "game development"}:
        return "game-development"

    ascii_topic = unicodedata.normalize("NFKD", topic).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_topic.casefold()).strip("-")[:48]
    if slug:
        return slug

    digest = hashlib.sha256(topic.encode("utf-8")).hexdigest()[:10]
    return f"topic-{digest}"


def _generic_candidates(topic: str, root_id: str) -> list[Candidate]:
    return [
        Candidate(
            id=f"{root_id}-{template.id}",
            label=template.label,
            domain=template.domain,
            description=template.description,
            connection=template.connection.format(topic=topic),
            relevance=template.relevance,
            novelty=template.novelty,
            cross_domain=template.cross_domain,
        )
        for template in GENERIC_TEMPLATES
    ]


def _fallback_candidates(topic: str, root_id: str) -> list[Candidate]:
    return (
        list(GAME_DEVELOPMENT_CANDIDATES)
        if topic.casefold() in {"游戏开发", "game development"}
        else _generic_candidates(topic, root_id)
    )


def _to_candidate(llm: LLMCandidate, fallback_index: int) -> Candidate:
    return Candidate(
        id=_candidate_label_id(llm.label),
        label=llm.label,
        domain=llm.domain,
        description=llm.description,
        connection=llm.connection,
        relevance=llm.relevance,
        novelty=llm.novelty,
        cross_domain=llm.cross_domain,
    )


def _deduplicate_fallback_against_llm(
    fallback: list[Candidate], llm_candidates: list[Candidate]
) -> list[Candidate]:
    return _deduplicate_fallback_against_existing(fallback, llm_candidates)


def _deduplicate_fallback_against_existing(
    fallback: list[Candidate], existing: list[Candidate]
) -> list[Candidate]:
    existing_ids = {candidate.id for candidate in existing}
    existing_labels = {_normalize_label(candidate.label) for candidate in existing}
    seen_ids: set[str] = set()
    seen_labels: set[str] = set()
    unique: list[Candidate] = []

    for candidate in fallback:
        normalized_label = _normalize_label(candidate.label)
        if (
            candidate.id in existing_ids
            or normalized_label in existing_labels
            or candidate.id in seen_ids
            or normalized_label in seen_labels
        ):
            continue
        seen_ids.add(candidate.id)
        seen_labels.add(normalized_label)
        unique.append(candidate)
    return unique


def _supplement_candidates_with_fallback(
    candidates: list[Candidate],
    fallback: list[Candidate],
    surprise_level: float,
    target_count: int = 6,
) -> tuple[list[Candidate], int]:
    needed = max(0, target_count - len(candidates))
    if needed == 0:
        return list(candidates), 0

    non_duplicate_fallback = _deduplicate_fallback_against_existing(fallback, candidates)
    ranked_fallback = select_top_candidates(
        non_duplicate_fallback,
        surprise_level,
        top_k=needed,
    )
    return [*candidates, *ranked_fallback], len(ranked_fallback)


def _update_generation_source(
    generation_source: str | None,
    fallback_added: int,
) -> str | None:
    if fallback_added == 0 or generation_source in {None, "fallback"}:
        return generation_source
    return "llm+fallback"


def _load_llm_service() -> LLMService | None:
    config = _load_llm_config()
    if not config.api_key or not config.base_url or not config.model:
        logger.info("LLM not configured; using fallback candidate generation.")
        return None
    logger.info(
        "LLM configured: model=%s base_url=%s", config.model, config.base_url
    )
    return LLMService(config=config)


def _llm_candidates_for_topic(topic: str) -> list[Candidate] | None:
    service = get_llm_service()
    if service is None:
        return None

    try:
        generation_result = service.get_candidates(topic)
    except Exception as exc:
        logger.warning("LLM candidate generation failed, using fallback: %s", exc)
        return None

    if not generation_result.candidates:
        return None

    return [_to_candidate(candidate, index) for index, candidate in enumerate(generation_result.candidates)]


def _explore_without_agent(request: ExploreRequest) -> ExploreResponse:
    root_id = _topic_id(request.topic)
    llm_candidates = _llm_candidates_for_topic(request.topic)
    fallback = _fallback_candidates(request.topic, root_id)

    generation_source: str | None = None
    candidates: list[Candidate] = []

    if llm_candidates is None:
        logger.info("Candidate source=fallback reason=llm_request_failed")
        generation_source = "fallback"
        candidates = fallback
    elif len(llm_candidates) < 6:
        logger.info(
            "Candidate source=fallback reason=insufficient_llm_candidates llm_candidates=%d",
            len(llm_candidates),
        )
        generation_source = "fallback"
        candidates = fallback
    elif len(llm_candidates) >= 12:
        candidates = llm_candidates
        generation_source = "llm"
        logger.info(
            "Candidate source=llm llm_candidates=%d fallback_added=0",
            len(llm_candidates),
        )
    else:
        supplemented = _deduplicate_fallback_against_llm(fallback, llm_candidates)
        candidates, _fallback_added = _supplement_candidates_with_fallback(
            llm_candidates,
            supplemented,
            request.surprise_level,
            target_count=12,
        )
        generation_source = "llm+fallback"
        logger.info(
            "Candidate source=llm+fallback llm_candidates=%d fallback_added=%d",
            len(llm_candidates),
            len(candidates) - len(llm_candidates),
        )

    selected = select_top_candidates(candidates, request.surprise_level)
    selected, fallback_added = _supplement_candidates_with_fallback(
        selected,
        fallback,
        request.surprise_level,
    )
    generation_source = _update_generation_source(generation_source, fallback_added)
    nodes = to_explore_nodes(selected)
    logger.info("Selected Top 6: %s", [node.label for node in selected[:6]])

    return ExploreResponse(
        root=ExploreRoot(id=root_id, label=request.topic),
        nodes=nodes,
        generation_source=generation_source,
        metadata=ExploreResponseMetadata(
            memory=None,
            agent_metrics=None,
        ),
    )


def explore_topic(request: ExploreRequest) -> ExploreResponse:
    if request.use_memory:
        response, _metrics = run_exploration(request)
        return response

    return _explore_without_agent(request)
