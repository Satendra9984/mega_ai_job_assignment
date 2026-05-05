"""REST endpoint: query persisted ROI records."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import ROIRecord, VideoSession
from app.pagination import decode_cursor, decode_snapshot, encode_cursor, encode_snapshot
from app.schemas.roi import ROIListResponse, ROIRecordRead

router = APIRouter()


@router.get("/roi", response_model=ROIListResponse)
async def list_roi(
    session_id: UUID = Query(..., description="Capture session UUID"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    use_cursor: bool = Query(False, description="Enable cursor pagination mode"),
    cursor: str | None = Query(None, description="Opaque cursor token from previous page"),
    snapshot: str | None = Query(
        None,
        description="Opaque snapshot token to freeze pagination under live writes",
    ),
    session: AsyncSession = Depends(get_db),
) -> ROIListResponse:
    vs = await session.get(VideoSession, session_id)
    if vs is None:
        raise HTTPException(status_code=404, detail="Session not found")

    base_filters = [ROIRecord.session_id == session_id]
    cursor_mode = use_cursor or cursor is not None or snapshot is not None
    snapshot_token: str | None = snapshot

    # Cursor pagination prevents duplicates/skips caused by live inserts during offset paging.
    if cursor_mode:
        if snapshot_token is None:
            max_id_stmt = (
                select(func.max(ROIRecord.id))
                .select_from(ROIRecord)
                .where(ROIRecord.session_id == session_id)
            )
            max_id = (await session.execute(max_id_stmt)).scalar_one()
            if max_id is not None:
                snapshot_token = encode_snapshot(max_id=int(max_id))
                base_filters.append(ROIRecord.id <= int(max_id))
        else:
            snap_max_id = decode_snapshot(snapshot_token)
            base_filters.append(ROIRecord.id <= snap_max_id)

        if cursor is not None:
            cursor_id = decode_cursor(cursor)
            base_filters.append(ROIRecord.id < cursor_id)

    count_stmt = select(func.count()).select_from(ROIRecord).where(*base_filters)
    total = int((await session.execute(count_stmt)).scalar_one())

    stmt = (
        select(ROIRecord)
        .where(*base_filters)
        .order_by(desc(ROIRecord.detected_at), desc(ROIRecord.id))
    )

    if cursor_mode:
        rows = (await session.execute(stmt.limit(limit + 1))).scalars().all()
        has_more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = None
        if has_more and rows:
            tail = rows[-1]
            next_cursor = encode_cursor(record_id=tail.id)
        effective_offset = 0
    else:
        rows = (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()
        has_more = offset + len(rows) < total
        next_cursor = None
        effective_offset = offset

    records = [ROIRecordRead.model_validate(r) for r in rows]

    return ROIListResponse(
        session_id=session_id,
        total=total,
        limit=limit,
        offset=effective_offset,
        has_more=has_more,
        next_cursor=next_cursor,
        snapshot=snapshot_token if cursor_mode else None,
        records=records,
    )
