"""add work_types to job_hunter_campaigns

Revision ID: i3j4k5l6m7n8
Revises: h2i3j4k5l6m7
Create Date: 2026-06-02 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = 'i3j4k5l6m7n8'
down_revision = 'h2i3j4k5l6m7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'job_hunter_campaigns',
        sa.Column('work_types', JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('job_hunter_campaigns', 'work_types')
