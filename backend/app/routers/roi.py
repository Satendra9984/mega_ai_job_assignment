"""REST endpoint: query persisted ROI records."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import ROIRecord, VideoSession
from app.schemas.roi import ROIListResponse, ROIRecordRead

router = APIRouter()


@router.get("/roi", response_model=ROIListResponse)
async def list_roi(
    session_id: UUID = Query(..., description="Capture session UUID"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> ROIListResponse:
    vs = await session.get(VideoSession, session_id)
    if vs is None:
        raise HTTPException(status_code=404, detail="Session not found")

    count_stmt = (
        select(func.count()).select_from(ROIRecord).where(ROIRecord.session_id == session_id)
    )
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = (
        select(ROIRecord)
        .where(ROIRecord.session_id == session_id)
        .order_by(ROIRecord.frame_index.asc())
        .offset(offset)
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()

    records = [ROIRecordRead.model_validate(r) for r in rows]

    return ROIListResponse(
        session_id=session_id,
        total=int(total),
        limit=limit,
        offset=offset,
        records=records,
    )
