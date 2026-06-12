"""
backend/main.py
---------------
FastAPI application factory.

Run with:
    cd backend
    uvicorn main:app --reload --port 8000
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load .env from project root (one level above backend/)
_root = Path(__file__).parent.parent
load_dotenv(_root / ".env")

# Also try a local .env inside backend/
load_dotenv(Path(__file__).parent / ".env")

from routers.chat import router as chat_router
from routers.admin import router as admin_router

# ── App creation ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="ShopEasy Refund Agent API",
    description="AI-powered customer support agent for processing e-commerce refunds.",
    version="1.0.0",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Allow the Vite dev server (port 5173) and any other origin during development

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # lock this down in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(chat_router, prefix="/api", tags=["chat"])
app.include_router(admin_router, prefix="/api", tags=["admin"])


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "service": "refund-agent"}


# ── Dev runner ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
