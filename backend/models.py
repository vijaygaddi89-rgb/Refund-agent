import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float,
    ForeignKey, Integer, JSON, String, Text,
)
from sqlalchemy.orm import relationship

from database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, nullable=False, index=True)
    customer_id = Column(String, nullable=True)
    customer_name = Column(String, nullable=True)
    customer_email = Column(String, nullable=True)
    status = Column(String, default="active")          # active | closed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship(
        "Message", back_populates="conversation",
        cascade="all, delete-orphan", order_by="Message.created_at",
    )
    refund_requests = relationship(
        "RefundRequest", back_populates="conversation",
        cascade="all, delete-orphan",
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False)   # user | assistant
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")


class RefundRequest(Base):
    __tablename__ = "refund_requests"

    id = Column(String, primary_key=True, default=_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    customer_id = Column(String, nullable=True, index=True)
    customer_name = Column(String, nullable=True)
    order_id = Column(String, nullable=True, index=True)
    product_name = Column(String, nullable=True)
    decision = Column(String, nullable=True)        # approved | denied | escalated
    refund_amount = Column(Float, nullable=True)
    denial_reason = Column(Text, nullable=True)
    policy_rule = Column(String, nullable=True)
    escalation_ticket = Column(String, nullable=True)
    reasoning_log = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

    conversation = relationship("Conversation", back_populates="refund_requests")