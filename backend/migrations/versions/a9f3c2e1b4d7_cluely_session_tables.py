"""cluely session tables

Revision ID: a9f3c2e1b4d7
Revises: da25c747a61b
Create Date: 2026-05-04 00:00:00.000000

Adds three cluely-specific tables for overlay session persistence:
  - cluely_sessions       — session metadata, linked to users + job_applications
  - cluely_transcript_lines — full speaker-labelled transcript
  - cluely_interactions   — every AI interaction (auto, manual, pill)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a9f3c2e1b4d7"
down_revision: Union[str, Sequence[str], None] = "da25c747a61b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cluely_sessions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("application_id", sa.String(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("company", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("role", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("post_summary", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_cluely_sessions_user_id_users")),
        # application_id references job_applications.id logically — no DB FK
        # because job_applications may not exist in all deployments.
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cluely_sessions")),
    )
    op.create_index("ix_cluely_sessions_user_id", "cluely_sessions", ["user_id"])
    op.create_index("ix_cluely_sessions_application_id", "cluely_sessions", ["application_id"])

    op.create_table(
        "cluely_transcript_lines",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("speaker", sa.String(length=20), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("spoken_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["cluely_sessions.id"],
            name=op.f("fk_cluely_transcript_lines_session_id_cluely_sessions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cluely_transcript_lines")),
    )
    op.create_index("ix_cluely_transcript_lines_session_id", "cluely_transcript_lines", ["session_id"])

    op.create_table(
        "cluely_interactions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("trigger_type", sa.String(length=20), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=True),
        sa.Column("inferred_outcome", sa.Text(), nullable=True),
        sa.Column("ai_response", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["cluely_sessions.id"],
            name=op.f("fk_cluely_interactions_session_id_cluely_sessions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cluely_interactions")),
    )
    op.create_index("ix_cluely_interactions_session_id", "cluely_interactions", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_cluely_interactions_session_id", table_name="cluely_interactions")
    op.drop_table("cluely_interactions")
    op.drop_index("ix_cluely_transcript_lines_session_id", table_name="cluely_transcript_lines")
    op.drop_table("cluely_transcript_lines")
    op.drop_index("ix_cluely_sessions_application_id", table_name="cluely_sessions")
    op.drop_index("ix_cluely_sessions_user_id", table_name="cluely_sessions")
    op.drop_table("cluely_sessions")
