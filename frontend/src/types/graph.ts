export interface GraphNodeData {
  id: string;
  label: string;
  domain: string;
  description: string;
  connection: string;
  surpriseScore: number;
  depth: number;
  isRoot: boolean;
  expanded: boolean;
}

export interface GraphEdgeData {
  id: string;
  source: string;
  target: string;
}

export type GraphGenerationState =
  | "idle"
  | "waiting"
  | "revealing"
  | "settling"
  | "complete"
  | "error";
