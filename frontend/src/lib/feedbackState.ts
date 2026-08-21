import type { FeedbackRecord, FeedbackValue } from "@/types/feedback";

export function getFeedbackKey(targetType: string, targetId: string): string {
  return `${targetType}:${targetId}`;
}

export function buildFeedbackMap(
  records: FeedbackRecord[],
): Record<string, FeedbackValue> {
  const map: Record<string, FeedbackValue> = {};
  for (const record of records) {
    map[getFeedbackKey(record.target_type, record.target_id)] = record.value;
  }
  return map;
}

export function upsertFeedbackRecord(
  records: FeedbackRecord[],
  record: FeedbackRecord,
): FeedbackRecord[] {
  const recordIndex = records.findIndex(
    (current) =>
      current.target_type === record.target_type &&
      current.target_id === record.target_id,
  );

  if (recordIndex === -1) {
    return [...records, record];
  }

  return records.map((current, index) =>
    index === recordIndex ? record : current,
  );
}

export function removeFeedbackRecord(
  records: FeedbackRecord[],
  targetType: string,
  targetId: string,
): FeedbackRecord[] {
  return records.filter(
    (record) =>
      record.target_type !== targetType || record.target_id !== targetId,
  );
}

function parseTimestamp(value: string): number | null {
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? null : timestamp;
}

export function sortFeedbackRecords(records: FeedbackRecord[]): FeedbackRecord[] {
  return [...records].sort((left, right) => {
    const updatedLeft = parseTimestamp(left.updated_at);
    const updatedRight = parseTimestamp(right.updated_at);
    if (updatedLeft !== null && updatedRight !== null && updatedLeft !== updatedRight) {
      return updatedRight - updatedLeft;
    }

    const createdLeft = parseTimestamp(left.created_at);
    const createdRight = parseTimestamp(right.created_at);
    if (createdLeft !== null && createdRight !== null && createdLeft !== createdRight) {
      return createdRight - createdLeft;
    }

    return right.id - left.id;
  });
}
