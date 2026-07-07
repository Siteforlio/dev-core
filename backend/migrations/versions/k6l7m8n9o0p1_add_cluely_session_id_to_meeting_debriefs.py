"""add cluely_session_id to meeting_debriefs

Revision ID: k6l7m8n9o0p1
Revises: j5k6l7m8n9o0
Create Date: 2026-07-06 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'k6l7m8n9o0p1'
down_revision = 'j5k6l7m8n9o0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'meeting_debriefs',
        sa.Column('cluely_session_id', sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('meeting_debriefs', 'cluely_session_id')
