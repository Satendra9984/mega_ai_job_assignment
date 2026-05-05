"""Database persistence helpers for ingest/session lifecycle."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ROIRecord, VideoSession
from app.services.detector import DetectionResult


async def create_session(db: AsyncSession) -> VideoSession:
    vs = VideoSession()
    db.add(vs)
    await db.commit()
    await db.refresh(vs)
    return vs


async def save_roi_record(
    db: AsyncSession,
    *,
    session_id: UUID,
    frame_index: int,
    result: DetectionResult,
) -> ROIRecord:
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
    await db.refresh(rec)
    return rec
