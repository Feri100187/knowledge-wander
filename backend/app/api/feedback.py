"""Feedback API routes."""

from fastapi import APIRouter, HTTPException, Query, Response

from app.models.feedback import FeedbackListResponse, FeedbackRecord, FeedbackUpsertRequest
from app.services import feedback_service


router = APIRouter(tags=["feedback"])


@router.put(
    "/feedback",
    response_model=FeedbackRecord,
    summary="Upsert feedback for a knowledge node or book",
)
def upsert_feedback(request: FeedbackUpsertRequest) -> FeedbackRecord:
    feedback_service.init_db()
    return feedback_service.upsert_feedback(request)


@router.get(
    "/feedback",
    response_model=FeedbackListResponse,
    summary="List active feedback for an anonymous user",
)
def list_feedback(
    anonymous_user_id: str = Query(min_length=1),
) -> FeedbackListResponse:
    feedback_service.init_db()
    records = feedback_service.list_feedback(anonymous_user_id)
    return FeedbackListResponse(feedbacks=records)


@router.delete(
    "/feedback/{target_type}/{target_id}",
    summary="Clear feedback for a target",
    status_code=204,
)
def delete_feedback(
    target_type: str,
    target_id: str,
    anonymous_user_id: str = Query(min_length=1),
) -> Response:
    feedback_service.init_db()
    if target_type not in {"knowledge_node", "book"}:
        raise HTTPException(status_code=422, detail="Invalid target_type")
    feedback_service.delete_feedback(anonymous_user_id, target_type, target_id)
    return Response(status_code=204)
