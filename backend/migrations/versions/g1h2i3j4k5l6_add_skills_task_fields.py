"""add skills_task fields: cheating_signals and task_brief on rounds

Revision ID: g1h2i3j4k5l6
Revises: a3b4c5d6e7f8
Create Date: 2026-05-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'g1h2i3j4k5l6'
down_revision = 'a3b4c5d6e7f8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('rounds', sa.Column('cheating_signals', JSONB, nullable=True))
    op.add_column('rounds', sa.Column('task_brief', JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column('rounds', 'task_brief')
    op.drop_column('rounds', 'cheating_signals')
