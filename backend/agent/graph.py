 
"""
graph.py
--------
The LangGraph state machine for the refund agent.

Graph shape:
  START → agent_node → (tool_node → agent_node)* → END

- agent_node: calls Claude with tools bound. Claude decides whether to
  call a tool or produce a final response.
- tool_node: executes whichever tool Claude chose and appends the result
  back into state.messages.
- The loop repeats until Claude stops calling tools (i.e., produces a
  plain text response = final answer).

This is the standard ReAct (Reason + Act) loop pattern.
"""

import json
from datetime import datetime
from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, ToolMessage, AIMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from agent.state import AgentState
from agent.tools import ALL_TOOLS
from agent.prompts import SYSTEM_PROMPT

# ── Model setup ───────────────────────────────────────────────────────────────
# Bind all tools to the model so Claude knows their schemas
_model = ChatAnthropic(
    model="claude-haiku-4-5-20251001",
    temperature=0,          # deterministic — we want consistent policy enforcement
    max_tokens=1024,
)
_model_with_tools = _model.bind_tools(ALL_TOOLS)


# ─────────────────────────────────────────────────────────────────────────────
# Node 1: agent_node
# Calls Claude. Claude either calls a tool or produces a final answer.
# ─────────────────────────────────────────────────────────────────────────────

def agent_node(state: AgentState) -> dict:
    """
    Core LLM node. Prepends the system prompt if this is the first turn,
    then calls Claude with the full message history.

    Returns a dict that LangGraph merges into state.
    """
    messages = state["messages"]

    # Always inject system prompt as the first message
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)

    # Call the model
    response = _model_with_tools.invoke(messages)

    # Emit a reasoning log entry for every agent turn
    log_entry = _build_log_entry(
        step=len(state.get("reasoning_log", [])) + 1,
        tool="agent_thinking",
        input_data={"last_user_message": _get_last_user_message(state["messages"])},
        output_data={
            "response_type": "tool_call" if response.tool_calls else "final_answer",
            "tool_calls": [tc["name"] for tc in response.tool_calls] if response.tool_calls else [],
            "content_preview": str(response.content)[:200] if response.content else "",
        },
    )

    return {
        "messages": [response],
        "reasoning_log": state.get("reasoning_log", []) + [log_entry],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Node 2: tool_node
# LangGraph's built-in ToolNode handles tool execution automatically.
# It reads the tool_calls from the last AIMessage, runs them, and
# appends ToolMessage results back into state.messages.
# ─────────────────────────────────────────────────────────────────────────────

def tool_node_with_logging(state: AgentState) -> dict:
    """
    Wraps LangGraph's ToolNode to add reasoning log entries for each tool call.
    """
    # Get the last AI message which contains tool_calls
    last_message = state["messages"][-1]
    tool_calls = getattr(last_message, "tool_calls", [])

    log_entries = []
    for tc in tool_calls:
        log_entry = _build_log_entry(
            step=len(state.get("reasoning_log", [])) + len(log_entries) + 1,
            tool=tc["name"],
            input_data=tc.get("args", {}),
            output_data="pending...",   # will be updated after execution
        )
        log_entries.append(log_entry)

    # Run the actual tools using LangGraph's built-in executor
    _tool_node = ToolNode(ALL_TOOLS)
    result = _tool_node.invoke(state)

    # Now update log entries with actual outputs
    tool_messages = [m for m in result.get("messages", []) if isinstance(m, ToolMessage)]
    for i, tm in enumerate(tool_messages):
        if i < len(log_entries):
            try:
                log_entries[i]["output"] = json.loads(tm.content)
            except Exception:
                log_entries[i]["output"] = tm.content

    return {
        "messages": result.get("messages", []),
        "reasoning_log": state.get("reasoning_log", []) + log_entries,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Edge: should_continue
# Decides whether to loop back to agent or stop.
# ─────────────────────────────────────────────────────────────────────────────

def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """
    Routing function called after agent_node.

    If the last message has tool_calls → go to tools node.
    If it's a plain text response → we're done, go to END.
    """
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "end"


# ─────────────────────────────────────────────────────────────────────────────
# Build the graph
# ─────────────────────────────────────────────────────────────────────────────

def build_graph():
    """
    Constructs and compiles the LangGraph state machine.

    Graph flow:
      START → agent → (if tool_calls) → tools → agent → ... → END
    """
    builder = StateGraph(AgentState)

    # Register nodes
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node_with_logging)

    # Edges
    builder.add_edge(START, "agent")

    # Conditional edge from agent: either call tools or finish
    builder.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",   # loop: go run the tools
            "end": END,         # done: return final response
        },
    )

    # After tools always go back to agent
    builder.add_edge("tools", "agent")

    return builder.compile()


# ── Singleton graph instance ──────────────────────────────────────────────────
# Compiled once at import time. Thread-safe for concurrent requests.
graph = build_graph()


# ─────────────────────────────────────────────────────────────────────────────
# Public API: run_agent
# ─────────────────────────────────────────────────────────────────────────────

def run_agent(user_message: str, history: list[dict] | None = None) -> dict:
    """
    Entry point called by the FastAPI chat router.

    Args:
        user_message: The customer's latest message
        history: Optional list of prior messages in {"role", "content"} format

    Returns:
        {
            "response": str,          # Claude's final reply to the customer
            "reasoning_log": list,    # all log entries from this run
            "final_decision": str,    # "approved" | "denied" | "partial" | "escalated" | None
        }
    """
    from langchain_core.messages import HumanMessage, AIMessage

    # Convert history to LangChain message objects
    lc_messages = []
    for msg in (history or []):
        if msg["role"] == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            lc_messages.append(AIMessage(content=msg["content"]))

    # Add current user message
    lc_messages.append(HumanMessage(content=user_message))

    # Initial state
    initial_state: AgentState = {
        "messages": lc_messages,
        "customer_id": None,
        "order_id": None,
        "customer_data": None,
        "order_data": None,
        "refund_reason": None,
        "policy_check_result": None,
        "final_decision": None,
        "reasoning_log": [],
    }

    # Run the graph
    final_state = graph.invoke(initial_state)

    # ── Extract Claude's final conversational reply ───────────────────────────
    # IMPORTANT: Must use isinstance(AIMessage) — ToolMessage and HumanMessage
    # also lack a `tool_calls` attribute so the old `hasattr` check was wrong.
    ai_response = ""
    for msg in reversed(final_state["messages"]):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            # Content can be a plain string or a list of blocks (Claude API)
            if isinstance(msg.content, str) and msg.content.strip():
                ai_response = msg.content
                break
            elif isinstance(msg.content, list):
                for block in msg.content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "").strip()
                        if text:
                            ai_response = text
                            break
                if ai_response:
                    break

    # ── Extract final_decision from the process_refund tool output ────────────
    # The state field isn't set by tools directly; read it from the log.
    final_decision = final_state.get("final_decision")
    if not final_decision:
        for entry in reversed(final_state.get("reasoning_log", [])):
            if entry.get("tool") == "process_refund":
                output = entry.get("output", {})
                if isinstance(output, dict) and output.get("decision"):
                    final_decision = output["decision"]
                    break

    return {
        "response": ai_response,
        "reasoning_log": final_state.get("reasoning_log", []),
        "final_decision": final_decision,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_log_entry(step: int, tool: str, input_data: dict, output_data) -> dict:
    return {
        "step": step,
        "tool": tool,
        "input": input_data,
        "output": output_data,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


def _get_last_user_message(messages: list) -> str:
    from langchain_core.messages import HumanMessage
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content[:200]
    return ""