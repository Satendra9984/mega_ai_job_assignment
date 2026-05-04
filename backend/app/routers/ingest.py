"""WebSocket endpoint: receive webcam frames, return ROI JSON, fan-out to frame bus."""

from __future__ import annotations

import asyncio
import functools
import logging
from typing import TYPE_CHECKING
from uuid import UUID

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

    session_id: UUID | None = None
    frame_index = 0

    try:
        try:
            async with session_factory() as db:  # type: AsyncSession
                vs = VideoSession()
                db.add(vs)
                await db.commit()
                await db.refresh(vs)
                session_id = vs.id
        except Exception:
            logger.exception("Ingest failed to create VideoSession")
            return

        logger.info("Ingest accepted session=%s", session_id)

        try:
            await websocket.send_json(
                {"type": "session", "session_id": str(session_id)},
            )
        except Exception:
            logger.exception(
                "Ingest handshake send_json failed session=%s",
                session_id,
            )
            return

        while True:
            message = await websocket.receive()

            if message.get("type") == "websocket.disconnect":
                break

            data = message.get("bytes")
            if data is None:
                continue

            if len(data) > settings.max_frame_bytes:
                try:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "code": "FRAME_TOO_LARGE",
                            "detail": f"Frame exceeds {settings.max_frame_bytes} bytes",
                        },
                    )
                except Exception:
                    logger.exception(
                        "Ingest send_json (FRAME_TOO_LARGE) failed session=%s",
                        session_id,
                    )
                    raise
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
                    try:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "code": "INVALID_FRAME",
                                "detail": "Could not decode as JPEG",
                            },
                        )
                    except Exception:
                        logger.exception(
                            "Ingest send_json (INVALID_FRAME) failed session=%s",
                            session_id,
                        )
                        raise
                else:
                    logger.exception("Detection ValueError")
                    try:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "code": "DETECTION_ERROR",
                                "detail": str(exc),
                            },
                        )
                    except Exception:
                        logger.exception(
                            "Ingest send_json (DETECTION_ERROR) failed session=%s",
                            session_id,
                        )
                        raise
                continue
            except Exception:
                logger.exception("Face detection failed")
                try:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "code": "DETECTION_ERROR",
                            "detail": "Internal detection error",
                        },
                    )
                except Exception:
                    logger.exception(
                        "Ingest send_json (DETECTION_ERROR generic) failed session=%s",
                        session_id,
                    )
                    raise
                continue

            try:
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
            except Exception:
                logger.exception(
                    "Ingest DB persist failed session=%s frame_index=%s",
                    session_id,
                    frame_index,
                )
                raise

            await frame_bus.publish(data)

            try:
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
            except Exception:
                logger.exception(
                    "Ingest send_json (roi) failed session=%s frame_index=%s",
                    session_id,
                    frame_index,
                )
                raise
            frame_index += 1

    except WebSocketDisconnect:
        logger.info("Ingest client disconnected session=%s", session_id)
    except Exception:
        logger.error(
            "Ingest handler terminating after exception session=%s frame_index=%s",
            session_id,
            frame_index,
        )
        try:
            await websocket.send_json(
                {
                    "type": "error",
                    "code": "INTERNAL",
                    "detail": "Server error; connection closing.",
                },
            )
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
