"""WebSocket endpoint: receive webcam frames, return ROI JSON, fan-out to frame bus."""

from __future__ import annotations

import asyncio
import functools
import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings
from app.models import ROIRecord, VideoSession
from app.services.detector import DetectionResult

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/ingest")
async def websocket_ingest(websocket: WebSocket) -> None:
    await websocket.accept()

    session_factory = websocket.app.state.session_factory
    detector = websocket.app.state.detector
    frame_bus = websocket.app.state.frame_bus

    async with session_factory() as db:  # type: AsyncSession
        vs = VideoSession()
        db.add(vs)
        await db.commit()
        await db.refresh(vs)
        session_id = vs.id

    await websocket.send_json(
        {"type": "session", "session_id": str(session_id)},
    )

    frame_index = 0

    try:
        while True:
            message = await websocket.receive()

            if message.get("type") == "websocket.disconnect":
                break

            data = message.get("bytes")
            if data is None:
                continue

            if len(data) > settings.max_frame_bytes:
                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "FRAME_TOO_LARGE",
                        "detail": f"Frame exceeds {settings.max_frame_bytes} bytes",
                    },
                )
                continue

            loop = asyncio.get_running_loop()
            try:
                result: DetectionResult = await loop.run_in_executor(
                    None,
                    functools.partial(detector.detect, data),
                )
            except ValueError as exc:
                code = str(exc)
                if code == "INVALID_JPEG" or code.startswith("INVALID_"):
                    await websocket.send_json(
                        {
                            "type": "error",
                            "code": "INVALID_FRAME",
                            "detail": "Could not decode as JPEG",
                        },
                    )
                else:
                    logger.exception("Detection ValueError")
                    await websocket.send_json(
                        {
                            "type": "error",
                            "code": "DETECTION_ERROR",
                            "detail": str(exc),
                        },
                    )
                continue
            except Exception:
                logger.exception("Face detection failed")
                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "DETECTION_ERROR",
                        "detail": "Internal detection error",
                    },
                )
                continue

            async with session_factory() as db:  # type: AsyncSession
                rec = ROIRecord(
                    session_id=session_id,
                    frame_index=frame_index,
                    face_detected=result.face_detected,
                    x=result.x,
                    y=result.y,
                    w=result.w,
                    h=result.h,
                    confidence=result.confidence,
                )
                db.add(rec)
                await db.commit()

            await frame_bus.publish(data)

            await websocket.send_json(
                {
                    "type": "roi",
                    "session_id": str(session_id),
                    "frame_index": frame_index,
                    "face_detected": result.face_detected,
                    "x": result.x,
                    "y": result.y,
                    "w": result.w,
                    "h": result.h,
                    "confidence": result.confidence,
                },
            )
            frame_index += 1

    except WebSocketDisconnect:
        logger.info("Ingest client disconnected session=%s", session_id)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
