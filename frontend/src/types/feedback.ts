export type FeedbackTargetType = "knowledge_node" | "book";
export type FeedbackValue = "like" | "dislike";

export interface FeedbackUpsertRequest {
  anonymous_user_id: string;
  target_type: FeedbackTargetType;
  target_id: string;
  target_label: string;
  target_domain: string;
  root_topic: string;
  value: FeedbackValue;
  surprise_level: number;
  generation_source?: string | null;
}

export interface FeedbackRecord extends FeedbackUpsertRequest {
  id: number;
  created_at: string;
  updated_at: string;
}

export interface FeedbackListResponse {
  feedbacks: FeedbackRecord[];
}
