import type {
  FeedbackListResponse,
  FeedbackRecord,
  FeedbackUpsertRequest,
} from "@/types/feedback";
import { buildApiUrl } from "@/lib/apiBaseUrl";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isFeedbackRecord(value: unknown): value is FeedbackRecord {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.id === "number" &&
    typeof value.anonymous_user_id === "string" &&
    typeof value.target_type === "string" &&
    typeof value.target_id === "string" &&
    typeof value.target_label === "string" &&
    typeof value.target_domain === "string" &&
    typeof value.root_topic === "string" &&
    typeof value.value === "string" &&
    typeof value.surprise_level === "number" &&
    typeof value.created_at === "string" &&
    typeof value.updated_at === "string"
  );
}

function isFeedbackListResponse(value: unknown): value is FeedbackListResponse {
  if (!isRecord(value) || !Array.isArray(value.feedbacks)) {
    return false;
  }
  return value.feedbacks.every(isFeedbackRecord);
}

export async function getFeedback(
  anonymousUserId: string,
): Promise<FeedbackListResponse> {
  const response = await fetch(
    buildApiUrl(`/api/feedback?anonymous_user_id=${encodeURIComponent(anonymousUserId)}`),
  );

  if (!response.ok) {
    throw new Error(`Feedback API returned ${response.status}`);
  }

  const payload: unknown = await response.json();
  if (!isFeedbackListResponse(payload)) {
    throw new Error("Feedback API returned an unexpected response shape");
  }

  return payload;
}

export async function setFeedback(
  request: FeedbackUpsertRequest,
): Promise<FeedbackRecord> {
  const response = await fetch(buildApiUrl("/api/feedback"), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Feedback API returned ${response.status}`);
  }

  const payload: unknown = await response.json();
  if (!isFeedbackRecord(payload)) {
    throw new Error("Feedback API returned an unexpected response shape");
  }

  return payload;
}

export async function deleteFeedback(
  targetType: string,
  targetId: string,
  anonymousUserId: string,
): Promise<void> {
  const response = await fetch(
    buildApiUrl(`/api/feedback/${encodeURIComponent(targetType)}/${encodeURIComponent(targetId)}?anonymous_user_id=${encodeURIComponent(anonymousUserId)}`),
    { method: "DELETE" },
  );

  if (!response.ok && response.status !== 204) {
    throw new Error(`Feedback API returned ${response.status}`);
  }
}
