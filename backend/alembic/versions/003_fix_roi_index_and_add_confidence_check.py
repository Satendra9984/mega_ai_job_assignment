"""fix roi index ordering and add confidence range check

Revision ID: 003
Revises: 002
Create Date: 2026-05-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_roi_records_session_detected_id_desc", table_name="roi_records")
    op.create_index(
        "ix_roi_records_session_detected_id_desc",
        "roi_records",
        ["session_id", sa.text("detected_at DESC"), sa.text("id DESC")],
    )
    op.create_check_constraint(
        "ck_confidence_range",
        "roi_records",
        "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_confidence_range", "roi_records", type_="check")
    op.drop_index("ix_roi_records_session_detected_id_desc", table_name="roi_records")
    op.create_index(
        "ix_roi_records_session_detected_id_desc",
        "roi_records",
        ["session_id", "detected_at", "id"],
    )
