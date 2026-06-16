from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str = Field(..., description="Unique browser/client session ID")
    message: str = Field(..., min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    conversation_id: str
    session_id: str
    message: str
    refund_decision: Optional[str] = None   # approved | denied | escalated | None
    refund_amount: Optional[float] = None
    reasoning_steps: List[Dict[str, Any]] = []
    error: Optional[str] = None


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationHistoryResponse(BaseModel):
    conversation_id: str
    session_id: str
    customer_id: Optional[str]
    customer_name: Optional[str]
    status: str
    created_at: datetime
    messages: List[MessageOut]


# ── Admin ─────────────────────────────────────────────────────────────────────

class ConversationSummary(BaseModel):
    id: str
    session_id: str
    customer_id: Optional[str]
    customer_name: Optional[str]
    status: str
    message_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RefundRequestOut(BaseModel):
    id: str
    conversation_id: str
    customer_id: Optional[str]
    customer_name: Optional[str]
    order_id: Optional[str]
    product_name: Optional[str]
    decision: Optional[str]
    refund_amount: Optional[float]
    denial_reason: Optional[str]
    policy_rule: Optional[str]
    escalation_ticket: Optional[str]
    reasoning_log: List[Dict[str, Any]]
    created_at: datetime
    processed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class AdminStats(BaseModel):
    total_conversations: int
    total_refund_requests: int
    approved: int
    denied: int
    escalated: int
    pending: int
    total_approved_amount: float


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    model: str
    db: str