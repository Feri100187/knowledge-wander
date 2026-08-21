"use client";

import { useEffect, useRef } from "react";
import cytoscape, { Core } from "cytoscape";
import type { ElementDefinition } from "cytoscape";

import { prefersReducedMotion } from "@/lib/motion";
import type { GraphGenerationState, GraphNodeData, GraphEdgeData } from "@/types/graph";

import styles from "./KnowledgeGraph.module.css";

const NODE_ENTRANCE_DURATION = 420;
const ROOT_ENTRANCE_DURATION = 260;
const EDGE_ENTRANCE_DURATION = 360;
const EDGE_HIGHLIGHT_DURATION = 620;
const SETTLE_DURATION = 760;

const stylesheet = [
  {
    selector: "node",
    style: {
      "background-color": "#24364b",
      label: "data(label)",
      color: "#eaf6fb",
      "font-size": "11.5px",
      "font-weight": "normal",
      "text-wrap": "wrap",
      "text-max-width": "112px",
      "text-valign": "bottom",
      "text-margin-y": "6px",
      "text-opacity": 1,
      "text-outline-color": "#081525",
      "text-outline-width": 2,
      width: "40px",
      height: "40px",
      opacity: 1,
      "border-width": 2,
      "border-color": "#38bdf8",
      "overlay-opacity": 0,
      "transition-property": "border-color, border-width, background-color",
      "transition-duration": "220ms",
    },
  },
  {
    selector: "node[isRoot = 1]",
    style: {
      width: "58px",
      height: "58px",
      "background-color": "#7546df",
      "border-color": "#b8a6ff",
      "font-size": "13px",
      "font-weight": "bold",
      "text-margin-y": "8px",
    },
  },
  {
    selector: "node.hovered",
    style: {
      "border-color": "#8eefff",
      "border-width": 3,
      "background-color": "#2c4058",
      "underlay-color": "#69dff6",
      "underlay-padding": 5,
      "underlay-opacity": 0.11,
      "underlay-shape": "ellipse",
    },
  },
  {
    selector: "node:selected",
    style: {
      "border-color": "#ff94cf",
      "border-width": 4,
      "background-color": "#3b348d",
      "underlay-color": "#f58bc6",
      "underlay-padding": 9,
      "underlay-opacity": 0.22,
      "underlay-shape": "ellipse",
    },
  },
  {
    selector: "node.generating",
    style: {
      "border-color": "#d5caff",
      "border-width": 3,
      "underlay-color": "#9c8cff",
      "underlay-padding": 15,
      "underlay-opacity": 0.18,
      "underlay-shape": "ellipse",
    },
  },
  {
    selector: "node.entering",
    style: {
      opacity: 0,
      width: "15px",
      height: "15px",
      "text-opacity": 0,
    },
  },
  {
    selector: "edge",
    style: {
      width: 1.9,
      "line-color": "#536d8b",
      "target-arrow-color": "#536d8b",
      "target-arrow-shape": "triangle",
      "curve-style": "bezier",
      "line-opacity": 0.9,
      opacity: 1,
      "overlay-opacity": 0,
    },
  },
  {
    selector: "edge.entering",
    style: {
      opacity: 0,
    },
  },
  {
    selector: "edge.revealed",
    style: {
      width: 2.6,
      "line-color": "#72e7f7",
      "target-arrow-color": "#a491ff",
      "line-opacity": 1,
    },
  },
] as unknown as cytoscape.StylesheetJson[];

interface KnowledgeGraphProps {
  nodes: GraphNodeData[];
  edges: GraphEdgeData[];
  selectedNodeId: string | null;
  onNodeSelect: (node: GraphNodeData) => void;
  graphKey: string;
  generationPhase?: GraphGenerationState;
  generatingNodeId?: string | null;
}

interface GraphPosition {
  x: number;
  y: number;
}

function nodeSize(node: GraphNodeData): number {
  return node.isRoot ? 58 : 40;
}

function animateNodeEntrance(
  node: cytoscape.NodeSingular,
  targetPosition: GraphPosition,
  data: GraphNodeData,
  reducedMotion: boolean,
) {
  node.addClass("entering");
  node.stop(true);

  const finalStyle = {
    opacity: 1,
    width: nodeSize(data),
    height: nodeSize(data),
    "text-opacity": 1,
  };

  if (reducedMotion) {
    node.position(targetPosition);
    node.style(finalStyle);
    node.removeClass("entering");
    return;
  }

  node.animate(
    {
      position: targetPosition,
      style: finalStyle,
    },
    {
      duration: data.isRoot ? ROOT_ENTRANCE_DURATION : NODE_ENTRANCE_DURATION,
      easing: "ease-out-cubic",
      queue: false,
      complete: () => node.removeClass("entering"),
    },
  );
}

function animateEdgeEntrance(
  edge: cytoscape.EdgeSingular,
  reducedMotion: boolean,
) {
  edge.addClass("entering revealed");
  edge.stop(true);

  if (reducedMotion) {
    edge.style({ opacity: 0.9 });
    edge.removeClass("entering revealed");
    return;
  }

  edge.animate(
    { style: { opacity: 0.9 } },
    {
      duration: EDGE_ENTRANCE_DURATION,
      easing: "ease-out-cubic",
      queue: false,
      complete: () => edge.removeClass("entering"),
    },
  );

  window.setTimeout(() => edge.removeClass("revealed"), EDGE_HIGHLIGHT_DURATION);
}

function fanOutPosition(
  parent: cytoscape.NodeSingular,
  node: GraphNodeData,
  edges: GraphEdgeData[],
): GraphPosition {
  const parentId = parent.id();
  const siblingEdges = edges.filter((edge) => edge.source === parentId);
  const siblingIndex = Math.max(
    0,
    siblingEdges.findIndex((edge) => edge.target === node.id),
  );
  const total = Math.max(1, siblingEdges.length);
  const angle = -Math.PI / 2 + (Math.PI * 2 * siblingIndex) / total;
  const radius = 148 + Math.min(node.depth * 18, 48);
  const parentPosition = parent.position();

  return {
    x: parentPosition.x + radius * Math.cos(angle),
    y: parentPosition.y + radius * Math.sin(angle),
  };
}

export default function KnowledgeGraph({
  nodes,
  edges,
  selectedNodeId,
  onNodeSelect,
  graphKey,
  generationPhase = "idle",
  generatingNodeId = null,
}: KnowledgeGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const nodesRef = useRef(nodes);
  const onNodeSelectRef = useRef(onNodeSelect);
  const knownElementIdsRef = useRef<Set<string>>(new Set());
  const settledPhaseRef = useRef(false);

  useEffect(() => {
    nodesRef.current = nodes;
  }, [nodes]);

  useEffect(() => {
    onNodeSelectRef.current = onNodeSelect;
  }, [onNodeSelect]);

  useEffect(() => {
    if (!containerRef.current) return;

    cyRef.current?.destroy();
    cyRef.current = null;
    knownElementIdsRef.current = new Set();
    settledPhaseRef.current = false;

    const cy = cytoscape({
      container: containerRef.current,
      elements: [],
      layout: { name: "preset", fit: false },
      style: stylesheet as unknown as cytoscape.StylesheetJson,
      minZoom: 0.2,
      maxZoom: 3,
      boxSelectionEnabled: false,
    });

    cy.on("tap", "node", (event) => {
      const data = event.target.data();
      const node = nodesRef.current.find((candidate) => candidate.id === data.id);
      if (node) {
        onNodeSelectRef.current(node);
      }
    });

    cy.on("mouseover", "node", (event) => {
      event.target.addClass("hovered");
      if (containerRef.current) {
        containerRef.current.style.cursor = "pointer";
      }
    });

    cy.on("mouseout", "node", (event) => {
      event.target.removeClass("hovered");
      if (containerRef.current) {
        containerRef.current.style.cursor = "grab";
      }
    });

    const resizeObserver = new ResizeObserver(() => cy.resize());
    resizeObserver.observe(containerRef.current);

    cyRef.current = cy;

    return () => {
      resizeObserver.disconnect();
      cy.stop();
      cyRef.current?.destroy();
      cyRef.current = null;
    };
  }, [graphKey]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    const reducedMotion = prefersReducedMotion();
    const desiredIds = new Set([
      ...nodes.map((node) => node.id),
      ...edges.map((edge) => edge.id),
    ]);
    const staleElements = cy
      .elements()
      .filter((element) => !desiredIds.has(element.id()));

    if (staleElements.length > 0) {
      staleElements.remove();
    }

    const existingIds = new Set(cy.elements().map((element) => element.id()));
    const newNodes = nodes.filter(
      (node) => !existingIds.has(node.id) && !knownElementIdsRef.current.has(node.id),
    );
    const newEdges = edges.filter(
      (edge) => !existingIds.has(edge.id) && !knownElementIdsRef.current.has(edge.id),
    );

    if (newNodes.length === 0 && newEdges.length === 0) {
      return;
    }

    const previousRoot = cy.nodes("[isRoot = 1]").first();
    const previousRootPosition = previousRoot.length
      ? { ...previousRoot.position() }
      : { x: 0, y: 0 };
    const nodeDefinitions: ElementDefinition[] = newNodes.map((node) => {
      const parentEdge = edges.find((edge) => edge.target === node.id);
      const parent = parentEdge ? cy.getElementById(parentEdge.source) : null;
      const sourcePosition = parent?.length
        ? parent.position()
        : node.isRoot
        ? previousRootPosition
        : { x: 0, y: 0 };
      // Cytoscape can retain the object returned by position(). Clone it so
      // siblings do not share a mutable starting position during entrance.
      const position = { x: sourcePosition.x, y: sourcePosition.y };

      return {
        group: "nodes",
        data: {
          id: node.id,
          label: node.label,
          isRoot: node.isRoot ? 1 : 0,
          depth: node.depth,
        },
        position,
      };
    });
    const edgeDefinitions: ElementDefinition[] = newEdges.map((edge) => ({
      group: "edges",
      data: {
        id: edge.id,
        source: edge.source,
        target: edge.target,
      },
    }));

    for (const node of newNodes) {
      knownElementIdsRef.current.add(node.id);
    }
    for (const edge of newEdges) {
      knownElementIdsRef.current.add(edge.id);
    }

    cy.add([...nodeDefinitions, ...edgeDefinitions]);

    if (newNodes.some((node) => node.isRoot) && cy.nodes().length === 1) {
      cy.fit(undefined, 48);
    }

    for (const nodeData of newNodes) {
      const node = cy.getElementById(nodeData.id);
      const parentEdge = edges.find((edge) => edge.target === nodeData.id);
      const parent = parentEdge ? cy.getElementById(parentEdge.source) : null;
      const targetPosition = parent?.length
        ? fanOutPosition(parent, nodeData, edges)
        : node.position();
      animateNodeEntrance(node, targetPosition, nodeData, reducedMotion);
    }

    for (const edgeData of newEdges) {
      const edge = cy.getElementById(edgeData.id);
      animateEdgeEntrance(edge, reducedMotion);
    }
  }, [edges, nodes]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    cy.elements().unselect();
    if (selectedNodeId) {
      const target = cy.getElementById(selectedNodeId);
      if (target.length > 0) {
        target.select();
      }
    }
  }, [selectedNodeId]);

  useEffect(() => {
    const cy = cyRef.current;
    const isGenerating =
      generationPhase === "waiting" ||
      generationPhase === "revealing" ||
      generationPhase === "settling";
    if (!cy || !isGenerating || !generatingNodeId) {
      return;
    }

    const target = cy.getElementById(generatingNodeId);
    if (!target.length) {
      return;
    }

    target.addClass("generating");
    const reducedMotion = prefersReducedMotion();
    if (reducedMotion) {
      return () => target.removeClass("generating");
    }

    let cancelled = false;
    const pulse = (opacity: number, padding: number, next: () => void) => {
      if (cancelled || !target.length) {
        return;
      }
      target.animate(
        {
          style: {
            "underlay-opacity": opacity,
            "underlay-padding": padding,
          },
        },
        {
          duration: 900,
          easing: "ease-in-out",
          queue: false,
          complete: next,
        },
      );
    };

    const loop = () => pulse(0.28, 18, () => pulse(0.14, 13, loop));
    loop();

    return () => {
      cancelled = true;
      target.stop(true);
      target.removeClass("generating");
    };
  }, [generationPhase, generatingNodeId, nodes.length]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || generationPhase !== "settling" || settledPhaseRef.current) {
      if (generationPhase !== "settling") {
        settledPhaseRef.current = false;
      }
      return;
    }

    settledPhaseRef.current = true;
    const reducedMotion = prefersReducedMotion();
    cy.nodes(".entering").stop(true, true).forEach((node) => {
      const data = node.data() as { isRoot?: number };
      node.removeClass("entering");
      node.style({
        opacity: 1,
        width: data.isRoot === 1 ? 58 : 40,
        height: data.isRoot === 1 ? 58 : 40,
        "text-opacity": 1,
      });
    });
    cy.edges(".entering").stop(true, true).removeClass("entering");
    cy.layout({
      name: "cose",
      randomize: true,
      animate: !reducedMotion,
      animationDuration: reducedMotion ? 0 : SETTLE_DURATION,
      padding: 48,
      fit: true,
    }).run();
  }, [generationPhase]);

  const runLayout = () => {
    const cy = cyRef.current;
    if (!cy) return;
    const reducedMotion = prefersReducedMotion();
    cy.layout({
      name: "cose",
      randomize: true,
      animate: !reducedMotion,
      animationDuration: reducedMotion ? 0 : SETTLE_DURATION,
      padding: 48,
      fit: true,
    }).run();
  };

  return (
    <div className={styles.wrapper}>
      <div
        ref={containerRef}
        className={styles.container}
        role="application"
        aria-label="交互式知识图谱，可拖动、缩放并点击节点查看详情"
        tabIndex={0}
      />
      <div className={styles.controls}>
        <button
          type="button"
          onClick={() => cyRef.current?.fit(undefined, 48)}
          className={styles.controlButton}
        >
          适应视图
        </button>
        <button type="button" onClick={runLayout} className={styles.controlButton}>
          重新布局
        </button>
      </div>
    </div>
  );
}
