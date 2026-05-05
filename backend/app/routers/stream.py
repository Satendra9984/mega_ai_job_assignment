"""Passive viewer WebSocket: receives raw JPEG frames from the frame bus."""

from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket) -> None:
    await websocket.accept()

    frame_bus = websocket.app.state.frame_bus
    session_id = websocket.query_params.get("session_id")
    queue = frame_bus.subscribe(session_id=session_id)

    try:
        while True:
            frame = await queue.get()
            if frame is None:
                break
            await websocket.send_bytes(frame)
    except WebSocketDisconnect:
        logger.info("Stream viewer disconnected")
    finally:
        frame_bus.unsubscribe(queue, session_id=session_id)
