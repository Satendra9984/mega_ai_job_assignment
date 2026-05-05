"""add composite index for ROI history pagination

Revision ID: 002
Revises: 001
Create Date: 2026-05-05
"""

from __future__ import annotations

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_roi_records_session_detected_id_desc",
        "roi_records",
        ["session_id", "detected_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_roi_records_session_detected_id_desc", table_name="roi_records")
