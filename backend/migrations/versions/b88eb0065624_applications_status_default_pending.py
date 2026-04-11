"""applications_status_default_pending

Revision ID: b88eb0065624
Revises: 59f7c25a2372
Create Date: 2026-04-11 20:07:53.956746

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b88eb0065624'
down_revision: Union[str, Sequence[str], None] = '59f7c25a2372'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "applications", "status",
        server_default="pending",
        existing_type=sa.String(20),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "applications", "status",
        server_default="applied",
        existing_type=sa.String(20),
        existing_nullable=False,
    )
