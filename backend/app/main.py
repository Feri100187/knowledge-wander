"""FastAPI application entry point."""

from contextlib import asynccontextmanager
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.explore import router as explore_router
from app.api.books import router as books_router
from app.api.feedback import router as feedback_router
from app.api.memory import router as memory_router
from app.services.feedback_service import init_db
from app.services.public_book_service import get_book_service
from app.services.memory_service import init_memory_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%H:%M:%S",
)


LOCAL_FRONTEND_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


def build_frontend_origins(configured_origin: str | None = None) -> list[str]:
    """Return explicit local and configured frontend origins without wildcards."""

    raw_origins = configured_origin
    if raw_origins is None:
        raw_origins = os.getenv("FRONTEND_ORIGIN", "")

    configured = [origin.strip().rstrip("/") for origin in raw_origins.split(",")]
    return list(dict.fromkeys([*LOCAL_FRONTEND_ORIGINS, *filter(None, configured)]))


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Prepare the shared SQLite schema before the first demo request."""

    db_path = init_db()
    init_memory_db(db_path)
    try:
        yield
    finally:
        await get_book_service().close()

app = FastAPI(
    title="Knowledge Wander API",
    description="Knowledge exploration API with surprise ranking, memory, and public book discovery.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=build_frontend_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)

app.include_router(explore_router, prefix="/api")
app.include_router(books_router, prefix="/api")
app.include_router(feedback_router, prefix="/api")
app.include_router(memory_router, prefix="/api")


@app.get("/health", tags=["system"], summary="Deployment health check")
def health() -> dict[str, str]:
    return {"status": "ok"}
