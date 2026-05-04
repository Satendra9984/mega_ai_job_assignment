from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ROIRecordRead(BaseModel):
    id: int
    frame_index: int
    detected_at: datetime
    face_detected: bool
    x: int | None
    y: int | None
    w: int | None
    h: int | None
    confidence: float | None

    model_config = {"from_attributes": True}


class ROIListResponse(BaseModel):
    session_id: UUID
    total: int
    limit: int = Field(ge=1, le=1000)
    offset: int = Field(ge=0)
    records: list[ROIRecordRead]
