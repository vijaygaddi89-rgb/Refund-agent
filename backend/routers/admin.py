"""
Admin dashboard API — read-only endpoints for monitoring conversations,
refund decisions, and agent reasoning logs.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models import Conversation, Message, RefundRequest
from schemas import AdminStats, ConversationSummary, RefundRequestOut
from agent.tools import find_customer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=AdminStats, summary="Dashboard summary statistics")
def get_stats(db: Session = Depends(get_db)) -> AdminStats:
    total_convs = db.query(func.count(Conversation.id)).scalar() or 0
    total_rr = db.query(func.count(RefundRequest.id)).scalar() or 0

    approved = (
        db.query(func.count(RefundRequest.id))
        .filter(RefundRequest.decision == "approved")
        .scalar() or 0
    )
    denied = (
        db.query(func.count(RefundRequest.id))
        .filter(RefundRequest.decision == "denied")
        .scalar() or 0
    )
    escalated = (
        db.query(func.count(RefundRequest.id))
        .filter(RefundRequest.decision == "escalated")
        .scalar() or 0
    )
    pending = total_rr - approved - denied - escalated

    total_amount = (
        db.query(func.sum(RefundRequest.refund_amount))
        .filter(RefundRequest.decision == "approved")
        .scalar() or 0.0
    )

    return AdminStats(
        total_conversations=total_convs,
        total_refund_requests=total_rr,
        approved=approved,
        denied=denied,
        escalated=escalated,
        pending=max(pending, 0),
        total_approved_amount=round(float(total_amount), 2),
    )


# ── Conversations ─────────────────────────────────────────────────────────────

@router.get(
    "/conversations",
    response_model=List[ConversationSummary],
    summary="List all conversations",
)
def list_conversations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None, description="Filter: active | closed"),
    db: Session = Depends(get_db),
) -> List[ConversationSummary]:
    q = db.query(Conversation)
    if status:
        q = q.filter(Conversation.status == status)
    convs = q.order_by(Conversation.updated_at.desc()).offset(skip).limit(limit).all()

    results = []
    for conv in convs:
        msg_count = db.query(func.count(Message.id)).filter(
            Message.conversation_id == conv.id
        ).scalar() or 0
        results.append(
            ConversationSummary(
                id=conv.id,
                session_id=conv.session_id,
                customer_id=conv.customer_id,
                customer_name=conv.customer_name,
                status=conv.status,
                message_count=msg_count,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
            )
        )
    return results


@router.get(
    "/conversations/{conversation_id}/reasoning",
    summary="Get reasoning log for a specific conversation",
)
def get_reasoning_log(
    conversation_id: str,
    db: Session = Depends(get_db),
) -> dict:
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    refund_requests = (
        db.query(RefundRequest)
        .filter(RefundRequest.conversation_id == conversation_id)
        .all()
    )

    all_steps = []
    for rr in refund_requests:
        all_steps.extend(rr.reasoning_log or [])

    return {
        "conversation_id": conversation_id,
        "customer_id": conv.customer_id,
        "customer_name": conv.customer_name,
        "reasoning_steps": all_steps,
        "refund_decisions": [
            {
                "order_id": rr.order_id,
                "decision": rr.decision,
                "refund_amount": rr.refund_amount,
                "policy_rule": rr.policy_rule,
                "processed_at": rr.processed_at,
            }
            for rr in refund_requests
        ],
    }


# ── Refund requests ───────────────────────────────────────────────────────────

@router.get(
    "/refunds",
    response_model=List[RefundRequestOut],
    summary="List all refund decisions",
)
def list_refunds(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    decision: Optional[str] = Query(None, description="Filter: approved | denied | escalated"),
    customer_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> List[RefundRequestOut]:
    q = db.query(RefundRequest)
    if decision:
        q = q.filter(RefundRequest.decision == decision)
    if customer_id:
        q = q.filter(RefundRequest.customer_id == customer_id)
    rows = q.order_by(RefundRequest.created_at.desc()).offset(skip).limit(limit).all()
    return [RefundRequestOut.model_validate(r) for r in rows]


@router.get(
    "/refunds/{refund_id}",
    response_model=RefundRequestOut,
    summary="Get a specific refund request",
)
def get_refund(refund_id: str, db: Session = Depends(get_db)) -> RefundRequestOut:
    rr = db.query(RefundRequest).filter(RefundRequest.id == refund_id).first()
    if not rr:
        raise HTTPException(status_code=404, detail="Refund request not found.")
    return RefundRequestOut.model_validate(rr)


# ── CRM overview ──────────────────────────────────────────────────────────────

@router.get("/customers", summary="List all CRM customers (from mock data)")
def list_crm_customers() -> dict:
    """Returns the CRM data for the admin dashboard."""
    import json
    from pathlib import Path
    crm_file = Path(__file__).parent.parent / "data" / "crm.json"
    if not crm_file.exists():
        raise HTTPException(status_code=404, detail="CRM data not found.")
    data = json.loads(crm_file.read_text())
    # Sanitize — remove sensitive fields if any
    return {"total": len(data["customers"]), "customers": data["customers"]}


@router.get("/customers/{identifier}", summary="Look up a specific CRM customer")
def get_crm_customer(identifier: str) -> dict:
    customer = find_customer(identifier)
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer '{identifier}' not found.")
    return customer