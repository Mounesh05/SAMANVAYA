"""
Real-time Broadcast & Event Service.
Provides Server-Sent Events (SSE) broadcasting to frontend dashboards
for automatic Kanban and AI feedback synchronization without manual page refreshes.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Set
from datetime import datetime, timezone

logger = logging.getLogger("samanvaya.realtime")


class RealtimeBroadcaster:
    """In-memory event hub for Server-Sent Events (SSE) broadcasting."""

    def __init__(self):
        self._listeners: Set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        """Register a new SSE client listener queue."""
        q = asyncio.Queue()
        self._listeners.add(q)
        logger.debug("[REALTIME] New listener connected. Total: %d", len(self._listeners))
        return q

    def unsubscribe(self, q: asyncio.Queue):
        """Remove an SSE client listener queue."""
        self._listeners.discard(q)
        logger.debug("[REALTIME] Listener disconnected. Total: %d", len(self._listeners))

    async def broadcast(self, event_type: str, data: Dict[str, Any]):
        """
        Dispatches an event to all connected frontend clients.
        Format matches W3C Server-Sent Events specification.
        """
        payload = {
            "event": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        msg = f"event: {event_type}\ndata: {json.dumps(payload, default=str)}\n\n"
        
        dead_queues = []
        for q in list(self._listeners):
            try:
                q.put_nowait(msg)
            except Exception:
                dead_queues.append(q)
        
        for dq in dead_queues:
            self._listeners.discard(dq)


# Global broadcaster singleton
broadcaster = RealtimeBroadcaster()
