from typing import TypedDict, Annotated, Optional, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """The state of the refund agent."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    session_id: str
    conversation_id: str
    customer_id: Optional[str]
    customer_name: Optional[str]
    refund_decision: Optional[str]
    refund_amount: Optional[float]
    collected_events: list[dict]
