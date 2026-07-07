"""add meeting_debriefs table

Revision ID: j5k6l7m8n9o0
Revises: 4234147b0733
Create Date: 2026-07-06 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'j5k6l7m8n9o0'
down_revision = 'c4d5e6f7a8b9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'meeting_debriefs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('calendar_event_uid', sa.String(512), nullable=True),
        sa.Column('date', sa.Date(), nullable=True),
        sa.Column('title', sa.String(512), nullable=False, server_default='Untitled meeting'),
        sa.Column('location', sa.String(512), nullable=True),
        sa.Column('start_time', sa.String(8), nullable=True),
        sa.Column('duration_minutes', sa.String(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('actions', JSONB(), nullable=False, server_default='[]'),
        sa.Column('decisions', JSONB(), nullable=False, server_default='[]'),
        sa.Column('attendees', JSONB(), nullable=False, server_default='[]'),
        sa.Column('ai_summary', sa.Text(), nullable=True),
        sa.Column('ai_summary_status', sa.String(16), nullable=False, server_default='none'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_meeting_debriefs_user_id', 'meeting_debriefs', ['user_id'])
    op.create_index('ix_meeting_debriefs_user_date', 'meeting_debriefs', ['user_id', 'date'])


def downgrade() -> None:
    op.drop_index('ix_meeting_debriefs_user_date', table_name='meeting_debriefs')
    op.drop_index('ix_meeting_debriefs_user_id', table_name='meeting_debriefs')
    op.drop_table('meeting_debriefs')
