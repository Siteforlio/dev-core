"""add behavioral signal columns

Revision ID: a3b4c5d6e7f8
Revises: f702822472ae
Create Date: 2026-05-15 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a3b4c5d6e7f8'
down_revision: Union[str, Sequence[str], None] = 'f702822472ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # RoundMoment — behavioral tracking columns
    op.add_column('round_moments', sa.Column('time_taken_seconds', sa.Integer(), nullable=True))
    op.add_column('round_moments', sa.Column('rewrite_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('round_moments', sa.Column('is_followup', sa.Boolean(), nullable=False, server_default='false'))
    # Round — time budget and holistic evaluation
    op.add_column('rounds', sa.Column('started_at', sa.DateTime(), nullable=True))
    op.add_column('rounds', sa.Column('time_budget_seconds', sa.Integer(), nullable=True))
    op.add_column('rounds', sa.Column('evaluation', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('round_moments', 'is_followup')
    op.drop_column('round_moments', 'rewrite_count')
    op.drop_column('round_moments', 'time_taken_seconds')
    op.drop_column('rounds', 'evaluation')
    op.drop_column('rounds', 'time_budget_seconds')
    op.drop_column('rounds', 'started_at')
