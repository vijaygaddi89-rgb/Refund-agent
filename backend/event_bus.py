"""
In-memory asyncio Queue-based event bus for SSE streaming.
Maps conversation_id → asyncio.Queue of events.
"""
import asyncio
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self) -> None:
        self._queues: Dict[str, asyncio.Queue] = {}

    def subscribe(self, conversation_id: str) -> asyncio.Queue:
        """Create or return a queue for this conversation."""
        if conversation_id not in self._queues:
            self._queues[conversation_id] = asyncio.Queue(maxsize=200)
        return self._queues[conversation_id]

    async def publish(self, conversation_id: str, event: dict) -> None:
        """Non-blocking publish. Drops the event if nobody is listening."""
        q = self._queues.get(conversation_id)
        if q is None:
            return
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("EventBus: queue full for %s — event dropped", conversation_id)

    async def publish_sentinel(self, conversation_id: str) -> None:
        """Signal the SSE generator to close."""
        await self.publish(conversation_id, {"type": "__close__"})

    def unsubscribe(self, conversation_id: str) -> None:
        self._queues.pop(conversation_id, None)


# Singleton — import this everywhere
event_bus = EventBus()