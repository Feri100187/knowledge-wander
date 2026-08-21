export interface ExploreRoot {
  id: string;
  label: string;
}

export interface ExploreNode {
  id: string;
  label: string;
  domain: string;
  description: string;
  connection: string;
  surprise_score: number;
}

export interface MemoryProfile {
  anonymous_user_id: string;
  preferred_domains: string[];
  disliked_domains: string[];
  liked_concepts: string[];
  disliked_concepts: string[];
  preferred_surprise_level: number;
  evidence_count: number;
  updated_at: string;
  memory_signature: string;
}

export interface MemoryProfileResponse {
  available: boolean;
  profile: MemoryProfile | null;
}

export interface AgentMetrics {
  memory_retrieval_ms: number;
  llm_latency_ms: number;
  total_latency_ms: number;
  candidate_cache_hit: boolean;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  memory_context_chars: number;
  changed_nodes_vs_baseline: number;
  exploration_ratio: number;
}

export interface ExploreResponseMetadata {
  memory: MemoryProfileResponse | null;
  agent_metrics: AgentMetrics | null;
}

export interface ExploreResponse {
  root: ExploreRoot;
  nodes: ExploreNode[];
  generation_source: string | null;
  metadata: ExploreResponseMetadata | null;
}

export interface ExploreRequest {
  topic: string;
  surprise_level: number;
  anonymous_user_id?: string | null;
  use_memory?: boolean;
}
