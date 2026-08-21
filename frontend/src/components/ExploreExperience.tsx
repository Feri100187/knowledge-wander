"use client";

import { useRef, useState, useCallback, useEffect, useMemo } from "react";
import type { FormEvent } from "react";

import { requestExploration, requestMemoryProfile } from "@/lib/exploreApi";
import { getOrCreateAnonymousUserId } from "@/lib/anonymousUser";
import { deleteFeedback, getFeedback, setFeedback } from "@/lib/feedbackApi";
import {
  buildFeedbackMap,
  getFeedbackKey,
  removeFeedbackRecord,
  upsertFeedbackRecord,
} from "@/lib/feedbackState";
import {
  BookApiError,
  requestBookAgentStream,
  requestBookRecommendation,
  searchBooks,
} from "@/lib/bookApi";
import type { FeedbackRecord, FeedbackValue } from "@/types/feedback";
import type {
  BookAgentBook,
  BookAgentPhase,
  BookAgentResponse,
  BookAgentStreamEvent,
  BookRecommendation,
  BookSearchResponse,
  BookWorkspaceTab,
} from "@/types/book";
import type {
  ExploreResponse,
  MemoryProfileResponse,
  AgentMetrics,
} from "@/types/explore";
import type {
  GraphGenerationState,
  GraphNodeData,
  GraphEdgeData,
} from "@/types/graph";

import KnowledgeGraph from "@/components/KnowledgeGraph/KnowledgeGraph";
import GraphGenerationStatus from "@/components/GraphGenerationStatus";
import MemoryEvidenceManager from "@/components/MemoryEvidenceManager";
import NodeDetailPanel from "@/components/NodeDetailPanel";

import styles from "./ExploreExperience.module.css";

const DEFAULT_TOPIC = "游戏开发";
const DEFAULT_SURPRISE_LEVEL = 50;
const MAX_GRAPH_NODES = 60;
const NODE_REVEAL_INTERVAL = 220;
const GRAPH_SETTLE_DURATION = 760;
const RECOMMENDED_TOPICS = ["摄影史", "游戏开发", "人工智能", "建筑"];

function getSurpriseHint(level: number): string {
  if (level <= 33) {
    return "更贴近当前主题";
  }
  if (level <= 66) {
    return "相关，但不显然";
  }
  return "更大胆的跨领域连接";
}

function createOptimisticRoot(label: string): GraphNodeData {
  return {
    id: `pending-root-${Date.now()}`,
    label,
    domain: "",
    description: "",
    connection: "",
    surpriseScore: 0,
    depth: 0,
    isRoot: true,
    expanded: false,
  };
}

function waitForRevealInterval(duration: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, duration);
  });
}

async function progressiveNodeReveal(
  nodes: GraphNodeData[],
  edges: GraphEdgeData[],
  append: (node: GraphNodeData, edge: GraphEdgeData) => void,
  onProgress: (revealedCount: number, totalCount: number) => void,
): Promise<void> {
  for (let index = 0; index < nodes.length; index += 1) {
    append(nodes[index], edges[index]);
    onProgress(index + 1, nodes.length);
    if (index < nodes.length - 1) {
      await waitForRevealInterval(NODE_REVEAL_INTERVAL);
    }
  }
}

export default function ExploreExperience() {
  const [topic, setTopic] = useState(DEFAULT_TOPIC);
  const [surpriseLevel, setSurpriseLevel] = useState(DEFAULT_SURPRISE_LEVEL);
  const [graphNodes, setGraphNodes] = useState<GraphNodeData[]>([]);
  const [graphEdges, setGraphEdges] = useState<GraphEdgeData[]>([]);
  const [graphGenerationState, setGraphGenerationState] =
    useState<GraphGenerationState>("idle");
  const [graphGenerationParentId, setGraphGenerationParentId] = useState<string | null>(null);
  const [graphGenerationMode, setGraphGenerationMode] = useState<"initial" | "expansion">(
    "initial",
  );
  const [graphGenerationSubject, setGraphGenerationSubject] = useState("");
  const [graphRevealCount, setGraphRevealCount] = useState(0);
  const [graphRevealTotal, setGraphRevealTotal] = useState<number | null>(null);
  const [graphSessionKey, setGraphSessionKey] = useState(0);
  const [selectedNode, setSelectedNode] = useState<GraphNodeData | null>(null);
  const [isInitialLoading, setIsInitialLoading] = useState(false);
  const [isExpanding, setIsExpanding] = useState(false);
  const [expandedNodeIds, setExpandedNodeIds] = useState<Set<string>>(new Set());
  const [expandError, setExpandError] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [generationSource, setGenerationSource] = useState<string | null>(null);
  const [books, setBooks] = useState<BookRecommendation[] | null>(null);
  const [activeBookTab, setActiveBookTab] =
    useState<BookWorkspaceTab>("recommendations");
  const [isDiscoveringBooks, setIsDiscoveringBooks] = useState(false);
  const [bookError, setBookError] = useState<string | null>(null);
  const [libraryAgentResult, setLibraryAgentResult] = useState<BookAgentResponse | null>(null);
  const [libraryAgentPhase, setLibraryAgentPhase] = useState<BookAgentPhase>("idle");
  const [libraryAgentEvents, setLibraryAgentEvents] = useState<BookAgentStreamEvent[]>([]);
  const [libraryAgentBooks, setLibraryAgentBooks] = useState<BookAgentBook[]>([]);
  const [libraryAgentError, setLibraryAgentError] = useState<string | null>(null);
  const [bookSearchQuery, setBookSearchQuery] = useState("Python");
  const [isBookSearching, setIsBookSearching] = useState(false);
  const [bookSearchResults, setBookSearchResults] = useState<BookSearchResponse | null>(null);
  const [bookSearchError, setBookSearchError] = useState<string | null>(null);
  const anonymousUserId = getOrCreateAnonymousUserId();
  const [feedbackMap, setFeedbackMap] = useState<Record<string, FeedbackValue>>({});
  const [feedbackRecords, setFeedbackRecords] = useState<FeedbackRecord[]>([]);
  const [nodeFeedbackPending, setNodeFeedbackPending] = useState(false);
  const [nodeFeedbackError, setNodeFeedbackError] = useState<string | null>(null);
  const [lastNodeFeedbackValue, setLastNodeFeedbackValue] = useState<FeedbackValue>("like");
  const [bookFeedbackPending, setBookFeedbackPending] = useState<Record<string, boolean>>({});
  const [bookFeedbackErrors, setBookFeedbackErrors] = useState<Record<string, string | null>>({});
  const [memoryProfile, setMemoryProfile] = useState<MemoryProfileResponse | null>(null);
  const [memoryLoading, setMemoryLoading] = useState(true);
  const [isMemoryInspectorOpen, setIsMemoryInspectorOpen] = useState(false);
  const [memoryDeletePending, setMemoryDeletePending] = useState<Record<string, boolean>>({});
  const [memoryDeleteErrors, setMemoryDeleteErrors] = useState<Record<string, string | null>>({});
  const [memoryActionNotice, setMemoryActionNotice] = useState<string | null>(null);
  const [useMemory, setUseMemory] = useState(true);
  const [agentMetrics, setAgentMetrics] = useState<AgentMetrics | null>(null);
  const requestInFlight = useRef(false);
  const graphSectionRef = useRef<HTMLElement>(null);
  const libraryWorkspaceRef = useRef<HTMLElement>(null);
  const shouldAutoScrollGraphRef = useRef(false);
  const libraryAgentBooksRef = useRef<BookAgentBook[]>([]);

  const scrollToLibraryWorkspace = useCallback(() => {
    window.setTimeout(() => {
      const workspace = libraryWorkspaceRef.current;
      if (!workspace || typeof workspace.scrollIntoView !== "function") {
        return;
      }
      const reduceMotion =
        typeof window.matchMedia === "function" &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const behavior = reduceMotion ? "auto" : "smooth";
      const detailArea = workspace.closest("aside") as HTMLElement | null;
      if (
        detailArea &&
        detailArea.scrollHeight > detailArea.clientHeight &&
        typeof detailArea.scrollTo === "function"
      ) {
        detailArea.scrollTo({
          top: Math.max(workspace.offsetTop - 12, 0),
          behavior,
        });
        return;
      }
      workspace.scrollIntoView({ behavior, block: "start" });
    }, 0);
  }, []);

  const isLibraryAgentRunning =
    libraryAgentPhase !== "idle" &&
    libraryAgentPhase !== "complete" &&
    libraryAgentPhase !== "error";

  const feedbackKey = useCallback(
    (targetType: string, targetId: string) => getFeedbackKey(targetType, targetId),
    [],
  );

  const upsertFeedbackInLocalState = useCallback((record: FeedbackRecord) => {
    const key = getFeedbackKey(record.target_type, record.target_id);
    setFeedbackMap((previous) => ({ ...previous, [key]: record.value }));
    setFeedbackRecords((previous) => upsertFeedbackRecord(previous, record));
    setMemoryDeleteErrors((previous) => ({ ...previous, [key]: null }));
  }, []);

  const removeFeedbackFromLocalState = useCallback(
    (targetType: string, targetId: string) => {
      const key = getFeedbackKey(targetType, targetId);
      setFeedbackMap((previous) => {
        const next = { ...previous };
        delete next[key];
        return next;
      });
      setFeedbackRecords((previous) =>
        removeFeedbackRecord(previous, targetType, targetId),
      );
      setMemoryDeleteErrors((previous) => {
        if (!(key in previous)) {
          return previous;
        }
        const next = { ...previous };
        delete next[key];
        return next;
      });
    },
    [],
  );

  const refreshMemory = useCallback(async () => {
    if (!anonymousUserId) {
      return;
    }

    setMemoryLoading(true);
    try {
      const profile = await requestMemoryProfile(anonymousUserId);
      setMemoryProfile(profile);
    } catch {
      setMemoryProfile(null);
    } finally {
      setMemoryLoading(false);
    }
  }, [anonymousUserId]);

  const currentPath = useMemo(() => {
    if (!selectedNode) {
      return [];
    }

    const labels = new Map(graphNodes.map((node) => [node.id, node.label]));
    const parents = new Map(graphEdges.map((edge) => [edge.target, edge.source]));
    const path: string[] = [];
    const visited = new Set<string>();
    let cursor: string | undefined = selectedNode.id;

    while (cursor && !visited.has(cursor)) {
      visited.add(cursor);
      const label = labels.get(cursor);
      if (label) {
        path.unshift(label);
      }
      cursor = parents.get(cursor);
    }

    return path;
  }, [selectedNode, graphNodes, graphEdges]);

  useEffect(() => {
    let cancelled = false;

    getFeedback(anonymousUserId)
      .then((response) => {
        if (cancelled) {
          return;
        }
        setFeedbackRecords(response.feedbacks);
        setFeedbackMap(buildFeedbackMap(response.feedbacks));
      })
      .catch(() => {
        // Non-blocking: feedback state restore is best-effort.
      });

    return () => {
      cancelled = true;
    };
  }, [anonymousUserId, feedbackKey]);

  useEffect(() => {
    if (graphNodes.length === 0 || !shouldAutoScrollGraphRef.current) {
      return;
    }

    shouldAutoScrollGraphRef.current = false;
    const scrollTimer = window.setTimeout(() => {
      const graphSection = graphSectionRef.current;
      if (!graphSection || typeof graphSection.scrollIntoView !== "function") {
        return;
      }
      const reduceMotion =
        typeof window.matchMedia === "function" &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      graphSection.scrollIntoView({
        behavior: reduceMotion ? "auto" : "smooth",
        block: "start",
      });
    }, 0);

    return () => window.clearTimeout(scrollTimer);
  }, [graphNodes.length]);

  useEffect(() => {
    if (!anonymousUserId) {
      return;
    }

    let cancelled = false;
    requestMemoryProfile(anonymousUserId)
      .then((profile) => {
        if (!cancelled) {
          setMemoryProfile(profile);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setMemoryProfile(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setMemoryLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [anonymousUserId]);

  const handleNodeFeedback = useCallback(
    async (value: FeedbackValue) => {
      if (!selectedNode || nodeFeedbackPending) {
        return;
      }
      const key = feedbackKey("knowledge_node", selectedNode.id);
      const current = feedbackMap[key];
      if (current === value) {
        setNodeFeedbackPending(true);
        setNodeFeedbackError(null);
        try {
          await deleteFeedback("knowledge_node", selectedNode.id, anonymousUserId);
          removeFeedbackFromLocalState("knowledge_node", selectedNode.id);
          await refreshMemory();
        } catch {
          setNodeFeedbackError("反馈删除失败，请重试。");
        } finally {
          setNodeFeedbackPending(false);
        }
        return;
      }

      setLastNodeFeedbackValue(value);
      setNodeFeedbackPending(true);
      setNodeFeedbackError(null);
      try {
        const record = await setFeedback({
          anonymous_user_id: anonymousUserId,
          target_type: "knowledge_node",
          target_id: selectedNode.id,
          target_label: selectedNode.label,
          target_domain: selectedNode.domain,
          root_topic: graphNodes[0]?.label ?? "",
          value,
          surprise_level: surpriseLevel / 100,
          generation_source: generationSource,
        });
        upsertFeedbackInLocalState(record);
        await refreshMemory();
      } catch {
        setNodeFeedbackError("反馈保存失败，请重试。");
      } finally {
        setNodeFeedbackPending(false);
      }
    },
    [
      selectedNode,
      nodeFeedbackPending,
      anonymousUserId,
      surpriseLevel,
      graphNodes,
      generationSource,
      feedbackMap,
      feedbackKey,
      removeFeedbackFromLocalState,
      refreshMemory,
      upsertFeedbackInLocalState,
    ],
  );

  const handleBookFeedback = useCallback(
    async (bookId: string, value: FeedbackValue) => {
      if (bookFeedbackPending[bookId]) {
        return;
      }
      const key = feedbackKey("book", bookId);
      const current = feedbackMap[key];
      if (current === value) {
        setBookFeedbackPending((prev) => ({ ...prev, [bookId]: true }));
        setBookFeedbackErrors((prev) => ({ ...prev, [bookId]: null }));
        try {
          await deleteFeedback("book", bookId, anonymousUserId);
          removeFeedbackFromLocalState("book", bookId);
          await refreshMemory();
        } catch {
          setBookFeedbackErrors((prev) => ({
            ...prev,
            [bookId]: "反馈删除失败，请重试。",
          }));
        } finally {
          setBookFeedbackPending((prev) => ({ ...prev, [bookId]: false }));
        }
        return;
      }

      setBookFeedbackPending((prev) => ({ ...prev, [bookId]: true }));
      setBookFeedbackErrors((prev) => ({ ...prev, [bookId]: null }));
      try {
        const book = books?.find((item) => item.id === bookId)
          ?? libraryAgentBooks.find((item) => item.book.id === bookId)?.book
          ?? libraryAgentResult?.books.find((item) => item.book.id === bookId)?.book;
        if (!book || !selectedNode) {
          return;
        }
        const record = await setFeedback({
          anonymous_user_id: anonymousUserId,
          target_type: "book",
          target_id: book.id,
          target_label: book.title,
          target_domain: selectedNode.domain,
          root_topic: graphNodes[0]?.label ?? "",
          value,
          surprise_level: surpriseLevel / 100,
          generation_source: generationSource,
        });
        upsertFeedbackInLocalState(record);
        await refreshMemory();
      } catch {
        setBookFeedbackErrors((prev) => ({
          ...prev,
          [bookId]: "反馈保存失败，请重试。",
        }));
      } finally {
        setBookFeedbackPending((prev) => ({ ...prev, [bookId]: false }));
      }
    },
    [
      anonymousUserId,
      bookFeedbackPending,
      books,
      libraryAgentBooks,
      libraryAgentResult,
      selectedNode,
      surpriseLevel,
      graphNodes,
      generationSource,
      feedbackMap,
      feedbackKey,
      removeFeedbackFromLocalState,
      refreshMemory,
      upsertFeedbackInLocalState,
    ],
  );

  const handleMemoryDelete = useCallback(
    async (record: FeedbackRecord) => {
      const key = feedbackKey(record.target_type, record.target_id);
      if (memoryDeletePending[key]) {
        return;
      }

      setMemoryDeletePending((previous) => ({ ...previous, [key]: true }));
      setMemoryDeleteErrors((previous) => ({ ...previous, [key]: null }));
      setMemoryActionNotice(null);
      try {
        await deleteFeedback(record.target_type, record.target_id, anonymousUserId);
        removeFeedbackFromLocalState(record.target_type, record.target_id);
        await refreshMemory();
        setMemoryActionNotice("已取消这条记忆。");
      } catch {
        setMemoryDeleteErrors((previous) => ({
          ...previous,
          [key]: "取消失败，请重试。",
        }));
      } finally {
        setMemoryDeletePending((previous) => ({ ...previous, [key]: false }));
      }
    },
    [
      anonymousUserId,
      feedbackKey,
      memoryDeletePending,
      refreshMemory,
      removeFeedbackFromLocalState,
    ],
  );

  const appendGraphElement = useCallback(
    (node: GraphNodeData, edge: GraphEdgeData) => {
      setGraphNodes((previous) => {
        if (previous.some((candidate) => candidate.id === node.id)) {
          return previous;
        }
        return [...previous, node];
      });
      setGraphEdges((previous) => {
        if (previous.some((candidate) => candidate.id === edge.id)) {
          return previous;
        }
        return [...previous, edge];
      });
    },
    [],
  );

  const resetLibraryAgentState = useCallback(() => {
    libraryAgentBooksRef.current = [];
    setLibraryAgentResult(null);
    setLibraryAgentPhase("idle");
    setLibraryAgentEvents([]);
    setLibraryAgentBooks([]);
    setLibraryAgentError(null);
  }, []);

  const handleInitialExplore = useCallback(
    async (normalizedTopic: string) => {
      const response: ExploreResponse = await requestExploration({
        topic: normalizedTopic,
        surprise_level: surpriseLevel / 100,
        anonymous_user_id: anonymousUserId,
        use_memory: useMemory,
      });

      setGenerationSource(response.generation_source ?? null);
      setAgentMetrics(response.metadata?.agent_metrics ?? null);
      setBooks(null);
      setBookError(null);
      setIsDiscoveringBooks(false);
      resetLibraryAgentState();

      const root: GraphNodeData = {
        id: response.root.id,
        label: response.root.label,
        domain: "",
        description: "",
        connection: "",
        surpriseScore: 0,
        depth: 0,
        isRoot: true,
        expanded: false,
      };

      const nodes: GraphNodeData[] = response.nodes.map((n) => ({
        id: n.id,
        label: n.label,
        domain: n.domain,
        description: n.description,
        connection: n.connection,
        surpriseScore: n.surprise_score,
        depth: 1,
        isRoot: false,
        expanded: false,
      }));

      const edges: GraphEdgeData[] = response.nodes.map((n) => ({
        id: `${root.id}--${n.id}`,
        source: root.id,
        target: n.id,
      }));

      setGraphNodes([root]);
      setGraphEdges([]);
      setGraphGenerationParentId(root.id);
      setGraphRevealCount(0);
      setGraphRevealTotal(nodes.length);
      setGraphGenerationState(nodes.length ? "revealing" : "settling");
      setExpandedNodeIds(new Set());
      setSelectedNode(null);
      setExpandError(null);

      // Let the root commit on its own before the first child is added. This
      // keeps the graph's first visual state honest and gives Cytoscape a real
      // parent position for the fan-out animation.
      await waitForRevealInterval(0);
      await progressiveNodeReveal(
        nodes,
        edges,
        appendGraphElement,
        (revealedCount, totalCount) => {
          setGraphRevealCount(revealedCount);
          setGraphRevealTotal(totalCount);
        },
      );
      await waitForRevealInterval(420);
      setGraphGenerationState("settling");
      await waitForRevealInterval(GRAPH_SETTLE_DURATION);
      setGraphGenerationState("complete");
      setGraphGenerationParentId(null);
    },
    [
      anonymousUserId,
      appendGraphElement,
      resetLibraryAgentState,
      surpriseLevel,
      useMemory,
    ],
  );

  const beginInitialExplore = useCallback(
    async (normalizedTopic: string) => {
      if (requestInFlight.current) {
        return;
      }

      const optimisticRoot = createOptimisticRoot(normalizedTopic);
      requestInFlight.current = true;
      shouldAutoScrollGraphRef.current = true;
      setGraphSessionKey((previous) => previous + 1);
      setGraphNodes([optimisticRoot]);
      setGraphEdges([]);
      setGraphGenerationState("waiting");
      setGraphGenerationMode("initial");
      setGraphGenerationParentId(optimisticRoot.id);
      setGraphGenerationSubject(normalizedTopic);
      setGraphRevealCount(0);
      setGraphRevealTotal(null);
      setGenerationSource(null);
      setAgentMetrics(null);
      setSelectedNode(null);
      setActiveBookTab("recommendations");
      setExpandedNodeIds(new Set());
      setExpandError(null);
      setError("");
      setBooks(null);
      setBookError(null);
      setIsDiscoveringBooks(false);
      resetLibraryAgentState();
      setIsInitialLoading(true);

      try {
        await handleInitialExplore(normalizedTopic);
      } catch {
        setError("暂时无法连接探索服务，请稍后重试。");
        setGraphGenerationState("error");
        setGraphGenerationParentId(null);
      } finally {
        requestInFlight.current = false;
        setIsInitialLoading(false);
      }
    },
    [handleInitialExplore, resetLibraryAgentState],
  );

  const handleExplore = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const normalizedTopic = topic.trim();
    if (!normalizedTopic) {
      setError("请先输入一个想探索的主题。");
      return;
    }

    void beginInitialExplore(normalizedTopic);
  };

  const handleNodeSelect = useCallback((node: GraphNodeData) => {
    setSelectedNode(node);
    setActiveBookTab("recommendations");
    setExpandError(null);
    setBooks(null);
    setBookError(null);
    setIsDiscoveringBooks(false);
    resetLibraryAgentState();
    setNodeFeedbackError(null);
    setBookFeedbackErrors({});
  }, [resetLibraryAgentState]);

  const handleExpand = async () => {
    if (!selectedNode || isExpanding) {
      return;
    }
    if (graphNodes.length >= MAX_GRAPH_NODES) {
      return;
    }
    if (expandedNodeIds.has(selectedNode.id)) {
      return;
    }

    setIsExpanding(true);
    setExpandError(null);
    setGraphGenerationMode("expansion");
    setGraphGenerationSubject(selectedNode.label);
    setGraphGenerationParentId(selectedNode.id);
    setGraphGenerationState("waiting");
    setGraphRevealCount(0);
    setGraphRevealTotal(null);

    try {
      const response = await requestExploration({
        topic: selectedNode.label,
        surprise_level: surpriseLevel / 100,
        anonymous_user_id: anonymousUserId,
        use_memory: useMemory,
      });

      const existingNodeIds = new Set(graphNodes.map((n) => n.id));
      const newNodes = response.nodes
        .filter((n) => !existingNodeIds.has(n.id))
        .map((n) => ({
          id: n.id,
          label: n.label,
          domain: n.domain,
          description: n.description,
          connection: n.connection,
          surpriseScore: n.surprise_score,
          depth: selectedNode.depth + 1,
          isRoot: false,
          expanded: false,
        }));

      const remainingSlots = MAX_GRAPH_NODES - graphNodes.length;
      const nodesToAdd = newNodes.slice(0, remainingSlots);

      const newEdges = nodesToAdd.map((n) => ({
        id: `${selectedNode.id}--${n.id}`,
        source: selectedNode.id,
        target: n.id,
      }));

      setGraphRevealTotal(nodesToAdd.length);
      setGraphGenerationState(nodesToAdd.length ? "revealing" : "settling");
      await progressiveNodeReveal(
        nodesToAdd,
        newEdges,
        appendGraphElement,
        (revealedCount, totalCount) => {
          setGraphRevealCount(revealedCount);
          setGraphRevealTotal(totalCount);
        },
      );
      await waitForRevealInterval(420);

      setExpandedNodeIds((prev) => {
        const next = new Set(prev);
        next.add(selectedNode.id);
        return next;
      });

      setGraphNodes((prev) =>
        prev.map((n) =>
          n.id === selectedNode.id ? { ...n, expanded: true } : n
        )
      );
      setSelectedNode((prev) =>
        prev?.id === selectedNode.id ? { ...prev, expanded: true } : prev
      );
      setGraphGenerationState("settling");
      await waitForRevealInterval(GRAPH_SETTLE_DURATION);
      setGraphGenerationState("complete");
      setGraphGenerationParentId(null);
    } catch {
      setExpandError("继续漫游暂时失败，请稍后重试。");
      setGraphGenerationState("error");
      setGraphGenerationParentId(null);
    } finally {
      setIsExpanding(false);
    }
  };

  const handleDiscoverBooks = useCallback(async () => {
    if (!selectedNode || selectedNode.isRoot) {
      return;
    }

    setActiveBookTab("recommendations");
    scrollToLibraryWorkspace();
    if (isDiscoveringBooks || (books !== null && !bookError)) {
      return;
    }

    setIsDiscoveringBooks(true);
    setBookError(null);
    setBooks(null);

    try {
      const response = await requestBookRecommendation({
        root_topic: graphNodes[0]?.label ?? "",
        node_label: selectedNode.label,
        node_domain: selectedNode.domain,
        surprise_level: surpriseLevel / 100,
      });
      setBooks(response.books);
      if (response.error_code === "NO_RESULTS" || response.books.length === 0) {
        setBookError(response.message ?? "暂未找到与该知识节点相关的公开图书。");
      }
    } catch (error) {
      if (error instanceof BookApiError) {
        setBookError(error.message);
      } else {
        setBookError("暂时无法加载公开图书推荐。");
      }
    } finally {
      setIsDiscoveringBooks(false);
    }
  }, [
    books,
    graphNodes,
    isDiscoveringBooks,
    bookError,
    scrollToLibraryWorkspace,
    selectedNode,
    surpriseLevel,
  ]);

  const handleBookAgent = useCallback(async () => {
    if (!selectedNode || selectedNode.isRoot) {
      return;
    }

    setActiveBookTab("agent");
    scrollToLibraryWorkspace();

    const hasAgentOutput =
      Boolean(libraryAgentResult) ||
      libraryAgentEvents.length > 0 ||
      libraryAgentBooks.length > 0;
    const isRetry = libraryAgentPhase === "error";
    if (isLibraryAgentRunning || (hasAgentOutput && !isRetry)) {
      return;
    }

    if (!isRetry) {
      libraryAgentBooksRef.current = [];
      setLibraryAgentEvents([]);
      setLibraryAgentBooks([]);
    }
    setLibraryAgentPhase("analyzing");
    setLibraryAgentError(null);
    if (!isRetry) {
      setLibraryAgentResult(null);
    }
    try {
      const request = {
        root_topic: graphNodes[0]?.label ?? selectedNode.label,
        node_label: selectedNode.label,
        node_domain: selectedNode.domain,
        current_path: currentPath.length ? currentPath : [selectedNode.label],
        surprise_level: surpriseLevel / 100,
      };
      await requestBookAgentStream(request, (event) => {
        setLibraryAgentEvents((previous) => [...previous, event]);
        if (event.type === "agent_started" || event.type === "path") {
          setLibraryAgentPhase("analyzing");
        } else if (event.type === "tool_call") {
          setLibraryAgentPhase("tool_call");
        } else if (event.type === "tool_result") {
          setLibraryAgentPhase("searching");
        } else if (event.type === "final_selection") {
          setLibraryAgentPhase("selecting");
        } else if (event.type === "book") {
          const nextBooks = libraryAgentBooksRef.current.some(
            (item) => item.book.id === event.book.id,
          )
            ? libraryAgentBooksRef.current
            : [...libraryAgentBooksRef.current, { book: event.book, reason: event.reason }];
          libraryAgentBooksRef.current = nextBooks;
          setLibraryAgentBooks(nextBooks);
          setLibraryAgentPhase("revealing_books");
        } else if (event.type === "complete") {
          setLibraryAgentResult({
            mode: event.metrics.mode,
            tool_used: event.metrics.tool_used,
            summary: event.summary,
            queries: event.metrics.queries,
            books: libraryAgentBooksRef.current,
            tool_trace: event.metrics.tool_trace,
            tool_calls: event.metrics.tool_calls,
            tool_latency_ms: event.metrics.tool_latency_ms,
            llm_rounds: event.metrics.llm_rounds,
            agent_total_latency_ms: event.metrics.agent_total_latency_ms,
            fallback_used: event.metrics.fallback_used,
          });
          setLibraryAgentPhase("complete");
        } else if (event.type === "error") {
          setLibraryAgentError(event.message);
          setLibraryAgentPhase("error");
        }
      });
    } catch (error) {
      if (error instanceof BookApiError) {
        setLibraryAgentError(error.message);
      } else {
        setLibraryAgentError("公开图书智能体暂时不可用，请稍后重试。");
      }
      setLibraryAgentPhase("error");
    }
  }, [
    currentPath,
    graphNodes,
    isLibraryAgentRunning,
    libraryAgentBooks,
    libraryAgentEvents,
    libraryAgentResult,
    libraryAgentPhase,
    scrollToLibraryWorkspace,
    selectedNode,
    surpriseLevel,
  ]);

  const handleBookSearch = useCallback(async () => {
    const normalizedQuery = bookSearchQuery.trim();
    if (!normalizedQuery || isBookSearching) {
      if (!normalizedQuery) {
        setBookSearchError("请输入书名、作者或关键词。");
      }
      return;
    }

    setIsBookSearching(true);
    setBookSearchError(null);
    try {
      const response = await searchBooks({
        q: normalizedQuery,
        limit: 10,
      });
      setBookSearchResults(response);
    } catch (error) {
      setBookSearchError(
        error instanceof BookApiError
          ? error.message
          : "公开图书检索失败，请稍后重试。",
      );
    } finally {
      setIsBookSearching(false);
    }
  }, [bookSearchQuery, isBookSearching]);

  const hasGraph = graphNodes.length > 0;
  const profileEvidenceCount = memoryProfile?.profile?.evidence_count ?? 0;
  const hasMemoryEvidence = memoryProfile?.available === true && profileEvidenceCount > 0;
  const graphKey = String(graphSessionKey);
  const activeBookFeedback: Record<string, FeedbackValue> = {};
  if (books) {
    for (const book of books) {
      const value = feedbackMap[`book:${book.id}`];
      if (value) {
        activeBookFeedback[book.id] = value;
      }
    }
  }
  if (libraryAgentResult) {
    for (const item of libraryAgentResult.books) {
      const value = feedbackMap[`book:${item.book.id}`];
      if (value) {
        activeBookFeedback[item.book.id] = value;
      }
    }
  }
  for (const item of libraryAgentBooks) {
    const value = feedbackMap[`book:${item.book.id}`];
    if (value) {
      activeBookFeedback[item.book.id] = value;
    }
  }

  return (
    <main className={styles.page}>
      <div className={styles.aurora} aria-hidden="true" />
      <div className={styles.grid} aria-hidden="true" />

      <div className={styles.shell}>
        <header className={styles.hero}>
          <div className={styles.eyebrow}>
            <span className={styles.pulse} />
            KNOWLEDGE WANDER · HACKATHON S2
          </div>
          <h1>
            <span className={styles.heroChinese}>知识漫游</span>
            <span className={styles.heroEnglish}>Knowledge Wander</span>
          </h1>
          <p className={styles.heroTagline}>别只找到你已经知道要找的东西。</p>
          <p className={styles.heroDescription}>
            在相关性与意外性之间主动控制知识距离，发现你原本不会搜索，
            <strong>却值得知道的知识</strong>。
          </p>
        </header>

        <section className={styles.explorer} aria-labelledby="explore-heading">
          <div className={styles.sectionHeading}>
            <div>
              <span className={styles.sectionKicker}>START A JOURNEY</span>
              <h2 id="explore-heading">今天，想从哪里开始漫游？</h2>
            </div>
            <div className={styles.topicExamples} aria-label="推荐演示主题">
              <span>推荐起点</span>
              {RECOMMENDED_TOPICS.map((recommendedTopic) => (
                <button
                  key={recommendedTopic}
                  className={styles.exampleButton}
                  type="button"
                  onClick={() => {
                    setTopic(recommendedTopic);
                    setError("");
                  }}
                >
                  {recommendedTopic}
                </button>
              ))}
            </div>
          </div>

          <form className={styles.form} onSubmit={handleExplore}>
            <div className={styles.fieldGroup}>
              <label htmlFor="topic">探索主题</label>
              <input
                id="topic"
                name="topic"
                type="text"
                value={topic}
                onChange={(event) => {
                  setTopic(event.target.value);
                  if (error) {
                    setError("");
                  }
                }}
                placeholder="今天想从哪里开始漫游？"
                maxLength={120}
                disabled={isInitialLoading}
                aria-describedby="topic-hint"
              />
              <span id="topic-hint">一个概念、问题或正在学习的领域</span>
            </div>

            <div className={styles.sliderGroup}>
              <div className={styles.sliderHeading}>
                <label htmlFor="surprise-level">意外度</label>
                <output htmlFor="surprise-level">{surpriseLevel}%</output>
              </div>
              <input
                id="surprise-level"
                name="surprise-level"
                type="range"
                min="0"
                max="100"
                step="1"
                value={surpriseLevel}
                onInput={(event) => setSurpriseLevel(Number(event.currentTarget.value))}
                disabled={isInitialLoading}
                aria-valuetext={`意外度 ${surpriseLevel}%`}
                aria-describedby="surprise-hint"
              />
              <div className={styles.sliderLabels} aria-hidden="true">
                <span>安全探索</span>
                <span>疯狂漫游</span>
              </div>
              <span id="surprise-hint" className={styles.surpriseHint}>
                {getSurpriseHint(surpriseLevel)}
              </span>
            </div>

            <button
              className={styles.exploreButton}
              type="submit"
              disabled={isInitialLoading}
              aria-busy={isInitialLoading}
            >
              <span>{isInitialLoading ? "正在寻找意外……" : "开始漫游"}</span>
              <span className={styles.arrow} aria-hidden="true">
                →
              </span>
            </button>

            <div className={styles.memoryBar}>
              <div className={styles.memorySummary}>
                <div className={styles.memoryBadge}>
                  <span
                    className={`${styles.memoryBadgeDot} ${!memoryProfile?.available ? styles.memoryBadgeDotInactive : ""}`}
                    aria-hidden="true"
                  />
                  {memoryLoading
                    ? "正在读取记忆…"
                    : hasMemoryEvidence && useMemory
                    ? `记忆已应用 · ${profileEvidenceCount} 条证据`
                    : hasMemoryEvidence
                    ? "记忆可用 · 当前关闭"
                    : "记忆尚未形成"}
                </div>
                <p>根据你的 👍 / 👎 调整探索，同时保留未知领域。</p>
              </div>
              <button
                className={styles.memoryToggle}
                type="button"
                onClick={() => setUseMemory((prev) => !prev)}
                disabled={memoryLoading}
                aria-pressed={useMemory}
              >
                <span>个性化记忆</span>
                <strong>{useMemory ? "开" : "关"}</strong>
              </button>
            </div>

            {hasMemoryEvidence && useMemory ? (
              <div className={styles.memoryInspector}>
                <MemoryEvidenceManager
                  records={feedbackRecords}
                  evidenceCount={feedbackRecords.length}
                  isOpen={isMemoryInspectorOpen}
                  pending={memoryDeletePending}
                  errors={memoryDeleteErrors}
                  actionNotice={memoryActionNotice}
                  onToggle={() => {
                    setIsMemoryInspectorOpen((previous) => !previous);
                    setMemoryActionNotice(null);
                  }}
                  onRemove={handleMemoryDelete}
                />
                <div className={styles.memoryInspectorGrid}>
                  <div>
                    <span className={styles.memoryLabel}>偏好领域</span>
                  {memoryProfile.profile?.preferred_domains?.length ? (
                    <ul className={styles.memoryList}>
                      {memoryProfile.profile.preferred_domains.map((domain) => (
                        <li key={domain} className={styles.memoryPill}>
                          {domain}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className={styles.memoryEmpty}>暂无偏好领域</p>
                  )}
                  </div>
                  <div>
                    <span className={styles.memoryLabel}>较少偏好</span>
                  {memoryProfile.profile?.disliked_domains?.length ? (
                    <ul className={styles.memoryList}>
                      {memoryProfile.profile.disliked_domains.map((domain) => (
                        <li key={domain} className={styles.memoryPill}>
                          {domain}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className={styles.memoryEmpty}>暂无较少偏好</p>
                  )}
                  </div>
                  <div className={styles.memoryStat}>
                    <span className={styles.memoryLabel}>偏好意外度</span>
                    <strong>
                      {Math.round((memoryProfile.profile?.preferred_surprise_level ?? 0.5) * 100)}%
                    </strong>
                  </div>
                  <div className={styles.memoryStat}>
                    <span className={styles.memoryLabel}>记忆证据</span>
                    <strong>{profileEvidenceCount} 条</strong>
                  </div>
                </div>
              </div>
            ) : null}
          </form>

          {error ? (
            <div className={styles.error} role="alert">
              <span aria-hidden="true">!</span>
              {error}
            </div>
          ) : null}

        </section>

        {hasGraph ? (
          <section ref={graphSectionRef} className={styles.graphSection} aria-live="polite">
            <div className={styles.graphSummary}>
              <div className={styles.graphSummaryTopline}>
                <div className={styles.badgeRow}>
                  {generationSource ? (
                    <span className={styles.sourceBadge}>
                      <span aria-hidden="true" />
                      {generationSource === "llm" && "AI 实时生成"}
                      {generationSource === "llm+fallback" && "AI + 离线补充"}
                      {generationSource === "fallback" && "离线候选"}
                    </span>
                  ) : null}
                  {useMemory && hasMemoryEvidence ? (
                    <span className={styles.memoryAppliedBadge}>
                      记忆已应用 · {profileEvidenceCount} 条证据
                    </span>
                  ) : null}
                </div>
                <span className={styles.graphSummaryTitle}>本次探索</span>
              </div>
              <GraphGenerationStatus
                state={graphGenerationState}
                subjectLabel={graphGenerationSubject || graphNodes[0]?.label || topic}
                isExpansion={graphGenerationMode === "expansion"}
                revealedCount={graphRevealCount}
                totalCount={graphRevealTotal}
                error={expandError || error || null}
                onRetry={
                  graphGenerationState === "error"
                    ? () => {
                        if (graphGenerationMode === "initial") {
                          const normalizedTopic = topic.trim();
                          if (normalizedTopic) {
                            void beginInitialExplore(normalizedTopic);
                          }
                        } else {
                          setExpandError(null);
                          void handleExpand();
                        }
                      }
                    : undefined
                }
              />
              {generationSource === "fallback" ? (
                <p className={styles.fallbackNotice} role="status">
                  AI 暂时没有响应，已切换到离线探索；图谱仍可继续使用。
                </p>
              ) : null}
              {agentMetrics ? (
                <div className={styles.metricsPanel} aria-label="本次探索指标">
                  <div
                    className={`${styles.metricItem} ${agentMetrics.candidate_cache_hit ? styles.metricHighlight : ""}`}
                  >
                    <span>候选缓存</span>
                    <strong>{agentMetrics.candidate_cache_hit ? "命中" : "未命中"}</strong>
                  </div>
                  <div
                    className={`${styles.metricItem} ${agentMetrics.candidate_cache_hit && agentMetrics.total_tokens === 0 ? styles.metricHighlight : ""}`}
                  >
                    <span>LLM Token</span>
                    <strong>
                      {agentMetrics.total_tokens == null
                        ? "Provider 未提供"
                        : agentMetrics.total_tokens.toLocaleString("zh-CN")}
                    </strong>
                  </div>
                  <div className={styles.metricItem}>
                    <span>LLM 耗时</span>
                    <strong>
                      {agentMetrics.llm_latency_ms > 0
                        ? `${(agentMetrics.llm_latency_ms / 1000).toFixed(1)}s`
                        : agentMetrics.candidate_cache_hit
                        ? "0s"
                        : "未调用"}
                    </strong>
                  </div>
                  <div className={styles.metricItem}>
                    <span>记忆检索</span>
                    <strong>{agentMetrics.memory_retrieval_ms.toFixed(1)}ms</strong>
                  </div>
                  <div className={styles.metricItem}>
                    <span>探索保留</span>
                    <strong>{Math.round(agentMetrics.exploration_ratio * 100)}%</strong>
                  </div>
                </div>
              ) : null}
            </div>
            <div className={styles.graphArea}>
              <KnowledgeGraph
                nodes={graphNodes}
                edges={graphEdges}
                selectedNodeId={selectedNode?.id ?? null}
                onNodeSelect={handleNodeSelect}
                graphKey={graphKey}
                generationPhase={graphGenerationState}
                generatingNodeId={graphGenerationParentId}
              />
            </div>
            <aside className={styles.detailArea}>
              <NodeDetailPanel
                node={selectedNode}
                currentPath={currentPath}
                isExpanding={isExpanding}
                expandError={expandError}
                maxNodesReached={graphNodes.length >= MAX_GRAPH_NODES}
                onContinueWander={handleExpand}
                onRetry={() => {
                  setExpandError(null);
                  handleExpand();
                }}
                onDiscoverBooks={
                  selectedNode && !selectedNode.isRoot ? handleDiscoverBooks : null
                }
                isDiscoveringBooks={isDiscoveringBooks}
                books={books}
                bookError={bookError}
                onRetryBooks={handleDiscoverBooks}
                onBookAgent={
                  selectedNode && !selectedNode.isRoot ? handleBookAgent : null
                }
                isBookAgentRunning={isLibraryAgentRunning}
                bookAgentResult={libraryAgentResult}
                bookAgentEvents={libraryAgentEvents}
                bookAgentBooks={libraryAgentBooks}
                bookAgentPhase={libraryAgentPhase}
                bookAgentError={libraryAgentError}
                onRetryBookAgent={handleBookAgent}
                activeBookTab={activeBookTab}
                onBookTabChange={setActiveBookTab}
                libraryWorkspaceRef={libraryWorkspaceRef}
                nodeFeedback={selectedNode && !selectedNode.isRoot ? feedbackMap[`knowledge_node:${selectedNode.id}`] ?? null : null}
                onNodeFeedback={handleNodeFeedback}
                isNodeFeedbackPending={nodeFeedbackPending}
                nodeFeedbackError={nodeFeedbackError}
                onRetryNodeFeedback={() => {
                  setNodeFeedbackError(null);
                  if (selectedNode) {
                    handleNodeFeedback(lastNodeFeedbackValue);
                  }
                }}
                bookFeedback={activeBookFeedback}
                onBookFeedback={handleBookFeedback}
                isBookFeedbackPending={bookFeedbackPending}
                bookFeedbackErrors={bookFeedbackErrors}
                onRetryBookFeedback={(bookId) => {
                  setBookFeedbackErrors((prev) => ({ ...prev, [bookId]: null }));
                  handleBookFeedback(bookId, feedbackMap[`book:${bookId}`] ?? "like");
                }}
                bookSearchQuery={bookSearchQuery}
                onBookSearchQueryChange={(value) => {
                  setBookSearchQuery(value);
                  setBookSearchError(null);
                }}
                isBookSearching={isBookSearching}
                onBookSearch={handleBookSearch}
                bookSearchResults={bookSearchResults}
                bookSearchError={bookSearchError}
              />
            </aside>
          </section>
        ) : null}

        <footer className={styles.footer}>
          Knowledge Wander · 知识漫游
        </footer>
      </div>
    </main>
  );
}
