"""
Real-time Server-Sent Events (SSE) Route.
Allows frontend dashboards (DevDashboard, DevOpsDashboard, QADashboard, Kanban)
to listen for live task updates, AI verification reports, and score changes.
"""

import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from domain.services.realtime_service import broadcaster

router = APIRouter()


@router.get("/stream")
@router.get("/events/stream", include_in_schema=False)
async def event_stream():
    """
    Subscribes client to live server-sent events.
    Heartbeats are sent every 15 seconds to keep the connection alive.
    """
    queue = broadcaster.subscribe()

    async def sse_generator():
        try:
            yield "event: connected\ndata: {\"status\": \"connected\"}\n\n"
            while True:
                try:
                    # Wait for next event or send heartbeat
                    msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield msg
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            broadcaster.unsubscribe(queue)

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

