"""
state.py
--------
Defines the shared state that flows through every node in the LangGraph graph.

LangGraph merges dicts returned by each node into this state object.
All keys are optional (None by default) so nodes can update only what they touch.
"""

from typing import Annotated, Optional
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    # ── Conversation messages (LangGraph managed) ─────────────────────────────
    # add_messages is a reducer: new messages are *appended*, not replaced
    messages: Annotated[list[BaseMessage], add_messages]

    # ── Customer / order context (set by lookup_customer tool) ────────────────
    customer_id: Optional[str]
    order_id: Optional[str]
    customer_data: Optional[dict]
    order_data: Optional[dict]

    # ── Refund request context (set by validate_policy tool) ──────────────────
    refund_reason: Optional[str]
    policy_check_result: Optional[dict]

    # ── Final outcome (set by process_refund tool) ────────────────────────────
    # One of: "approved" | "denied" | "partial" | "escalated" | None
    final_decision: Optional[str]

    # ── Agent reasoning trace (appended by every node) ────────────────────────
    # Each entry is a dict: {step, tool, input, output, timestamp}
    reasoning_log: list