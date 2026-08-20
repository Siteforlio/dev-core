"""add url index to job_listings

Revision ID: m8n9o0p1q2r3
Revises: l7m8n9o0p1q2
Create Date: 2026-07-14 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op

revision: str = 'm8n9o0p1q2r3'
down_revision: Union[str, Sequence[str], None] = 'l7m8n9o0p1q2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # CONCURRENTLY not supported inside a transaction block in Alembic by default,
    # but we use it here via execute() which runs outside the implicit transaction.
    op.execute("CREATE INDEX IF NOT EXISTS ix_job_listings_url ON job_listings (url text_pattern_ops)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_job_listings_apply_url ON job_listings (apply_url text_pattern_ops)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_job_listings_url")
    op.execute("DROP INDEX IF EXISTS ix_job_listings_apply_url")
