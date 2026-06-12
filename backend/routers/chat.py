"""
routers/chat.py
---------------
FastAPI router for the customer-facing chat interface.

Endpoints:
  POST /api/chat          → single-turn request/response (simple polling UI)
  WebSocket /api/ws/{id} → real-time streaming of agent reasoning steps
"""

import asyncio
import json
import uuid
from typing import List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

# Import the agent runner (runs in a thread pool since it's sync)
from agent.graph import run_agent

router = APIRouter()


# ── Request / Response models ─────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str       # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = []


class ChatResponse(BaseModel):
    response: str
    reasoning_log: list
    final_decision: Optional[str] = None
    session_id: str


# ── REST endpoint ─────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Synchronous chat endpoint.
    Runs the full LangGraph agent loop and returns when complete.
    """
    history_dicts = [
        {"role": msg.role, "content": msg.content}
        for msg in (request.history or [])
    ]

    # Run in thread pool so we don't block the event loop
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: run_agent(request.message, history_dicts)
    )

    return ChatResponse(
        response=result["response"],
        reasoning_log=result["reasoning_log"],
        final_decision=result.get("final_decision"),
        session_id=str(uuid.uuid4()),
    )


# ── WebSocket endpoint ────────────────────────────────────────────────────────

class ConnectionManager:
    """Manages active WebSocket connections."""
    def __init__(self):
        self.active: dict[str, WebSocket] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active[session_id] = websocket

    def disconnect(self, session_id: str):
        self.active.pop(session_id, None)

    async def send_json(self, session_id: str, data: dict):
        ws = self.active.get(session_id)
        if ws:
            await ws.send_json(data)


manager = ConnectionManager()


@router.websocket("/ws/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time streaming.

    Message protocol (client → server):
        { "message": "...", "history": [...] }

    Message protocol (server → client):
        { "type": "log",      "data": { log entry } }   ← reasoning step
        { "type": "response", "data": { response, final_decision } }
        { "type": "error",    "data": { "message": "..." } }
        { "type": "status",   "data": { "status": "processing"|"done" } }
    """
    await manager.connect(session_id, websocket)

    try:
        while True:
            # Wait for a message from the client
            raw = await websocket.receive_text()
            payload = json.loads(raw)

            user_message = payload.get("message", "")
            history = payload.get("history", [])

            # Notify client that processing has started
            await websocket.send_json({"type": "status", "data": {"status": "processing"}})

            # Run agent in thread pool
            loop = asyncio.get_event_loop()

            try:
                result = await loop.run_in_executor(
                    None,
                    lambda: run_agent(user_message, history)
                )

                # Stream each reasoning log entry
                for log_entry in result["reasoning_log"]:
                    await websocket.send_json({"type": "log", "data": log_entry})
                    await asyncio.sleep(0.05)  # small delay for visual streaming effect

                # Send final response
                await websocket.send_json({
                    "type": "response",
                    "data": {
                        "response": result["response"],
                        "final_decision": result.get("final_decision"),
                    }
                })

            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "data": {"message": str(e)}
                })

            # Notify done
            await websocket.send_json({"type": "status", "data": {"status": "done"}})

    except WebSocketDisconnect:
        manager.disconnect(session_id)
