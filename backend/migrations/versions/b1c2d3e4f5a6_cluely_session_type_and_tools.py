"""cluely_sessions: add session_type and tools_used

Revision ID: b1c2d3e4f5a6
Revises: a9f3c2e1b4d7
Create Date: 2026-05-10 00:00:00.000000

Adds two columns to cluely_sessions:
  - session_type  VARCHAR(20) — "present" | "coding" | "live" | "ai_model"
  - tools_used    JSON        — list of distinct tool names used in the session
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "a9f3c2e1b4d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "cluely_sessions",
        sa.Column("session_type", sa.String(20), nullable=True),
    )
    op.add_column(
        "cluely_sessions",
        sa.Column("tools_used", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cluely_sessions", "tools_used")
    op.drop_column("cluely_sessions", "session_type")
