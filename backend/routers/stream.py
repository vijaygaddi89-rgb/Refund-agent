"""
Server-Sent Events (SSE) endpoint for real-time agent reasoning logs.
Frontend connects here to receive live events as the agent processes.
"""
import asyncio
import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from event_bus import event_bus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stream", tags=["stream"])

HEARTBEAT_INTERVAL = 15  # seconds


@router.get(
    "/{session_id}",
    summary="SSE stream of real-time agent reasoning events",
    response_class=StreamingResponse,
)
async def stream_events(session_id: str) -> StreamingResponse:
    """
    Connect to this endpoint to receive real-time agent reasoning events.

    Event types:
      - processing_started  — agent received the message
      - tool_call           — agent is calling a tool (with tool name + input)
      - tool_result         — tool returned a result (preview)
      - complete            — agent finished processing
      - error               — agent encountered an error
      - heartbeat           — keep-alive ping
    """
    queue = event_bus.subscribe(session_id)

    async def generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL)
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                    continue

                if event.get("type") == "__close__":
                    break

                yield f"data: {json.dumps(event)}\n\n"

                if event.get("type") == "complete":
                    break

        except asyncio.CancelledError:
            logger.debug("SSE connection cancelled for %s", session_id)
        finally:
            event_bus.unsubscribe(session_id)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",   # Disable nginx buffering
        },
    )