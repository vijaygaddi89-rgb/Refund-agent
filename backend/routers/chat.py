import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from agent.graph import process_message
from database import get_db
from models import Conversation, Message
from schemas import ChatRequest, ChatResponse, ConversationHistoryResponse, MessageOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "/message",
    response_model=ChatResponse,
    summary="Send a message to the AI support agent",
)
async def send_message(
    request: ChatRequest,
    db: Session = Depends(get_db),
) -> ChatResponse:
    """
    Send a user message and receive the agent's response.
    The agent will autonomously look up customer data, check policy,
    and approve/deny/escalate refund requests.
    """
    if not request.message.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message cannot be empty.",
        )

    try:
        return await process_message(
            session_id=request.session_id,
            user_message=request.message.strip(),
            db=db,
        )
    except Exception as exc:
        logger.error("Error in /chat/message: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Agent processing failed. Please try again.",
        )


@router.get(
    "/{conversation_id}/history",
    response_model=ConversationHistoryResponse,
    summary="Retrieve full conversation history",
)
def get_history(
    conversation_id: str,
    db: Session = Depends(get_db),
) -> ConversationHistoryResponse:
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    return ConversationHistoryResponse(
        conversation_id=conv.id,
        session_id=conv.session_id,
        customer_id=conv.customer_id,
        customer_name=conv.customer_name,
        status=conv.status,
        created_at=conv.created_at,
        messages=[MessageOut.model_validate(m) for m in conv.messages],
    )


@router.delete(
    "/{conversation_id}",
    summary="Close/end a conversation",
)
def close_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
) -> dict:
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    conv.status = "closed"
    db.commit()
    return {"status": "closed", "conversation_id": conversation_id}