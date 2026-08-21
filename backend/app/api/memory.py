"""Memory API route."""

from fastapi import APIRouter

from app.models.memory import MemoryProfileResponse
from app.services.memory_service import ensure_memory

router = APIRouter(tags=["memory"])


@router.get(
    "/memory",
    response_model=MemoryProfileResponse,
    summary="Get user memory profile",
)
def get_memory_profile(anonymous_user_id: str | None = None) -> MemoryProfileResponse:
    if not anonymous_user_id:
        return MemoryProfileResponse(available=False, profile=None)

    profile = ensure_memory(anonymous_user_id)
    if profile is None:
        return MemoryProfileResponse(available=False, profile=None)
    return MemoryProfileResponse(available=True, profile=profile)
