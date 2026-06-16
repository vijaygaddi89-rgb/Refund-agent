"""
backend/agent/graph.py
-----------------------
Orchestration layer between FastAPI routers and the LangGraph agent.

Uses LangGraph with ChatLiteLLM.
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from sqlalchemy.orm import Session

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langgraph.prebuilt import create_react_agent

from database import get_db, SessionLocal, settings
from event_bus import event_bus
from models import Conversation, Message, RefundRequest
from schemas import ChatResponse
from agent.state import AgentState
from agent.tools import AGENT_TOOLS
from agent.prompts import SYSTEM_PROMPT

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

logger = logging.getLogger(__name__)

MODEL = os.getenv("MODEL_NAME", "gpt-4o")

# ── LangGraph Definition ────────────────────────────────────────────────────────

# Initialize model using the provider string natively supported by Langchain
llm = init_chat_model(MODEL, max_tokens=1024)
app_graph = create_react_agent(llm, tools=AGENT_TOOLS, prompt=SYSTEM_PROMPT)


# ── Conversation helpers ───────────────────────────────────────────────────────

def get_or_create_conversation(session_id: str, db: Session) -> Conversation:
    conv = (
        db.query(Conversation)
        .filter(Conversation.session_id == session_id, Conversation.status == "active")
        .first()
    )
    if not conv:
        conv = Conversation(id=str(uuid.uuid4()), session_id=session_id)
        db.add(conv)
        db.commit()
        db.refresh(conv)
    return conv


def _save_message(conv_id: str, role: str, content: str, db: Session) -> Message:
    msg = Message(conversation_id=conv_id, role=role, content=content)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


# ── Event helpers ─────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _emit(session_id: str, event_type: str, data: dict) -> None:
    """Push an event to the SSE event bus. Never raises."""
    try:
        await event_bus.publish(session_id, {
            "type": event_type,
            "data": data,
            "timestamp": _now_iso(),
        })
    except Exception as e:
        logger.warning("Event emit failed (%s): %s", event_type, e)


# ── Public API ─────────────────────────────────────────────────────────────────

async def process_message(
    session_id: str,
    user_message: str,
    db: Session,
) -> ChatResponse:
    # 1. Conversation
    conv = get_or_create_conversation(session_id, db)
    conversation_id = conv.id

    await event_bus.publish(session_id, {
        "type": "processing_started",
        "message": user_message[:100],
        "timestamp": _now_iso(),
    })

    # 2. Save user message
    _save_message(conversation_id, "user", user_message, db)
    db.refresh(conv)

    # 3. Build message history
    initial_messages = []
    for msg in conv.messages:
        if msg.role == "user":
            initial_messages.append(HumanMessage(content=msg.content))
        else:
            initial_messages.append(AIMessage(content=msg.content))

    state = {
        "messages": initial_messages,
        "session_id": session_id,
        "conversation_id": conversation_id,
        "customer_id": conv.customer_id,
        "customer_name": conv.customer_name,
        "refund_decision": None,
        "refund_amount": None,
        "collected_events": []
    }

    # 4. Run LangGraph loop
    event_bus.subscribe(conversation_id)
    collected_events = []
    assistant_text = ""
    iteration = 0

    await _emit(session_id, "thinking", {
        "message": f"Agent starting — preparing to process refund request using {MODEL}...",
    })

    try:
        async for update in app_graph.astream(state, stream_mode="updates"):
            if "agent" in update:
                iteration += 1
                await _emit(session_id, "thinking", {
                    "message": f"Calling LLM ({MODEL}, iteration {iteration})...",
                    "iteration": iteration,
                })
                
                msg = update["agent"]["messages"][0]
                
                llm_event = {
                    "type": "llm_response",
                    "iteration": iteration,
                    "content": msg.content or "",
                }
                await _emit(session_id, "llm_response", llm_event)
                collected_events.append(llm_event)
                
                if getattr(msg, "tool_calls", None):
                    for tc in msg.tool_calls:
                        call_event = {
                            "tool_name": tc["name"],
                            "tool_input": tc["args"],
                            "tool_use_id": tc["id"],
                        }
                        await _emit(session_id, "tool_call", call_event)
                        collected_events.append({"type": "tool_call", **call_event})
                else:
                    # Final answer
                    assistant_text = msg.content or "Your request has been processed."
                    
            elif "tools" in update:
                msgs = update["tools"]["messages"]
                for msg in msgs:
                    result = getattr(msg, "artifact", None)
                    if result is None:
                        try:
                            result = json.loads(msg.content)
                        except Exception:
                            import ast
                            try:
                                result = ast.literal_eval(msg.content)
                            except Exception:
                                result = msg.content

                    result_event = {
                        "tool_name": msg.name,
                        "result": result,
                        "tool_use_id": msg.tool_call_id,
                    }
                    await _emit(session_id, "tool_result", result_event)
                    collected_events.append({"type": "tool_result", **result_event})
                    
    except Exception as e:
        logger.exception("Agent loop error for session %s: %s", session_id, e)
        assistant_text = "An unexpected error occurred. Please try again."
        await _emit(session_id, "error", {"message": str(e)})
    finally:
        if assistant_text:
            await _emit(session_id, "final_answer", {"text": assistant_text, "session_id": session_id})
            collected_events.append({"type": "final_answer", "text": assistant_text, "session_id": session_id})
            
        await event_bus.publish(session_id, {
            "type": "complete",
            "timestamp": _now_iso(),
        })

    # 5. Save assistant response
    if assistant_text:
        _save_message(conversation_id, "assistant", assistant_text, db)

    # 6. Update conversation context
    customer_id: Optional[str] = conv.customer_id
    customer_name: Optional[str] = conv.customer_name
    refund_decision: Optional[str] = None
    refund_amount: Optional[float] = None

    for ev in collected_events:
        if ev.get("type") == "tool_result":
            result = ev.get("result", {})
            if isinstance(result, dict):
                if result.get("customer_id"):
                    customer_id = result["customer_id"]
                if result.get("customer_name"):
                    customer_name = result["customer_name"]
                if result.get("decision"):
                    refund_decision = result["decision"]
                if result.get("refund_amount") is not None:
                    refund_amount = result["refund_amount"]

    if customer_id and customer_id != conv.customer_id:
        conv.customer_id = customer_id
    if customer_name and customer_name != conv.customer_name:
        conv.customer_name = customer_name
    db.commit()

    # 7. Persist refund request if a decision was reached
    if refund_decision:
        _persist_refund_request(
            conv=conv,
            customer_id=customer_id,
            customer_name=customer_name,
            refund_decision=refund_decision,
            refund_amount=refund_amount,
            collected_events=collected_events,
            db=db,
        )

    # 8. Persist event trace
    await _save_trace(session_id, collected_events)

    return ChatResponse(
        conversation_id=conversation_id,
        session_id=session_id,
        message=assistant_text,
        refund_decision=refund_decision,
        refund_amount=refund_amount,
        reasoning_steps=collected_events,
        error=None,
    )


# ── Persistence helpers ────────────────────────────────────────────────────────

def _persist_refund_request(
    conv: Conversation,
    customer_id: Optional[str],
    customer_name: Optional[str],
    refund_decision: str,
    refund_amount: Optional[float],
    collected_events: list,
    db: Session,
) -> None:
    existing = (
        db.query(RefundRequest)
        .filter(
            RefundRequest.conversation_id == conv.id,
            RefundRequest.decision == refund_decision,
        )
        .first()
    )
    if existing:
        return

    rr = RefundRequest(
        conversation_id=conv.id,
        customer_id=customer_id,
        customer_name=customer_name,
        decision=refund_decision,
        refund_amount=refund_amount,
        reasoning_log=collected_events,
        processed_at=datetime.utcnow(),
    )
    db.add(rr)
    db.commit()
    logger.info(
        "Refund request saved: conversation=%s decision=%s",
        conv.id, refund_decision,
    )


async def _save_trace(session_id: str, events: list[dict]) -> None:
    try:
        trace_json = json.dumps(events, default=str)
        db = SessionLocal()
        try:
            record = db.query(RefundRequest).filter(
                RefundRequest.conversation_id.in_(
                    db.query(Conversation.id).filter(Conversation.session_id == session_id)
                )
            ).first()
            if record:
                record.reasoning_log = events
                db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.warning("Could not save trace for session %s: %s", session_id, e)
