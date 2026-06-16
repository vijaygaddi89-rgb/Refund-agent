"""
FastAPI application entry point.
"""
import logging
from contextlib import asynccontextmanager

import httpx
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import create_tables, settings
from routers import admin, chat, stream
from schemas import HealthResponse

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Refund Agent API...")
    create_tables()
    logger.info("Database tables ready.")
    yield
    logger.info("Shutting down Refund Agent API.")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AI Customer Support Agent — Refund Processing",
    description=(
        "LangGraph-powered refund agent that processes e-commerce refund requests "
        "strictly according to company policy. Backed by a mock CRM with 15 customer profiles."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(chat.router)
app.include_router(stream.router)
app.include_router(admin.router)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        model=os.getenv("MODEL_NAME", "gpt-4o"),
        db=settings.DATABASE_URL,
    )


@app.get("/", tags=["health"])
async def root() -> dict:
    return {
        "service": "AI Refund Support Agent",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


# ── Dev runner ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )