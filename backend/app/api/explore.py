"""Explore API route."""

from fastapi import APIRouter

from app.models.explore import ExploreRequest, ExploreResponse
from app.services.explore_service import explore_topic


router = APIRouter(tags=["explore"])


@router.post(
    "/explore",
    response_model=ExploreResponse,
    summary="Generate mock cross-domain exploration nodes",
)
def explore(request: ExploreRequest) -> ExploreResponse:
    return explore_topic(request)
