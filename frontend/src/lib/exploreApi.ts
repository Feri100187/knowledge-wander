import type {
  ExploreNode,
  ExploreRequest,
  ExploreResponse,
  MemoryProfileResponse,
} from "@/types/explore";
import { buildApiUrl } from "@/lib/apiBaseUrl";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isExploreNode(value: unknown): value is ExploreNode {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.id === "string" &&
    typeof value.label === "string" &&
    typeof value.domain === "string" &&
    typeof value.description === "string" &&
    typeof value.connection === "string" &&
    typeof value.surprise_score === "number"
  );
}

function isExploreResponse(value: unknown): value is ExploreResponse {
  if (!isRecord(value) || !isRecord(value.root) || !Array.isArray(value.nodes)) {
    return false;
  }

  return (
    typeof value.root.id === "string" &&
    typeof value.root.label === "string" &&
    value.nodes.every(isExploreNode)
  );
}

export async function requestExploration(
  request: ExploreRequest,
): Promise<ExploreResponse> {
  const response = await fetch(buildApiUrl("/api/explore"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Explore API returned ${response.status}`);
  }

  const payload: unknown = await response.json();
  if (!isExploreResponse(payload)) {
    throw new Error("Explore API returned an unexpected response shape");
  }

  return payload;
}

export async function requestMemoryProfile(
  anonymousUserId: string | null | undefined,
): Promise<MemoryProfileResponse> {
  const query = anonymousUserId
    ? `?anonymous_user_id=${encodeURIComponent(anonymousUserId)}`
    : "";

  const response = await fetch(buildApiUrl(`/api/memory${query}`), {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Memory API returned ${response.status}`);
  }

  const payload: unknown = await response.json();
  if (!isRecord(payload) || typeof payload.available !== "boolean") {
    throw new Error("Memory API returned an unexpected response shape");
  }

  return payload as unknown as MemoryProfileResponse;
}
