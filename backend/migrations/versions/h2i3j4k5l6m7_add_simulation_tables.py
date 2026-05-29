"""add simulation tables and drop user_progress session_id FK

Revision ID: h2i3j4k5l6m7
Revises: g1h2i3j4k5l6
Create Date: 2026-05-28 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'h2i3j4k5l6m7'
down_revision = '1a19ea887bc8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'simulation_sessions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('scenario_type', sa.String(50), nullable=True),
        sa.Column('brief', JSONB(), nullable=True),
        sa.Column('attachments', JSONB(), nullable=False, server_default='[]'),
        sa.Column('time_budget_seconds', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('hard_cutoff_fired', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('persona', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'simulation_turns',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('seq', sa.Integer(), nullable=False),
        sa.Column('speaker', sa.String(10), nullable=False),
        sa.Column('modality', sa.String(10), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('audio_url', sa.String(512), nullable=True),
        sa.Column('time_offset_seconds', sa.Integer(), server_default='0', nullable=False),
        sa.Column('tool_calls', JSONB(), nullable=False, server_default='[]'),
        sa.Column('emotion_state', sa.String(50), nullable=True),
        sa.Column('rewrite_count', sa.Integer(), server_default='0', nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'simulation_debriefs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('scenario_type', sa.String(50), nullable=True),
        sa.Column('overall_score', sa.Float(), nullable=True),
        sa.Column('hire_signal', sa.String(20), nullable=True),
        sa.Column('core_scores', JSONB(), nullable=True),
        sa.Column('scenario_scores', JSONB(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('strengths', JSONB(), nullable=False, server_default='[]'),
        sa.Column('improvements', JSONB(), nullable=False, server_default='[]'),
        sa.Column('focus_areas', JSONB(), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # Drop FK constraint on user_progress.session_id so simulation session IDs
    # don't cause violations (simulation_sessions != interview sessions table).
    # The column stays as a plain String — logical link only.
    # Use raw SQL with a savepoint so a missing constraint doesn't abort the transaction.
    conn = op.get_bind()
    conn.execute(sa.text("SAVEPOINT drop_fk_savepoint"))
    try:
        conn.execute(sa.text(
            "ALTER TABLE user_progress DROP CONSTRAINT user_progress_session_id_fkey"
        ))
        conn.execute(sa.text("RELEASE SAVEPOINT drop_fk_savepoint"))
    except Exception:
        conn.execute(sa.text("ROLLBACK TO SAVEPOINT drop_fk_savepoint"))


def downgrade() -> None:
    op.drop_table('simulation_debriefs')
    op.drop_table('simulation_turns')
    op.drop_table('simulation_sessions')
    op.create_foreign_key(
        'user_progress_session_id_fkey',
        'user_progress', 'sessions',
        ['session_id'], ['id'],
    )
