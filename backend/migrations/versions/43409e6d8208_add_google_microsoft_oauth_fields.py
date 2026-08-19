"""add_google_microsoft_oauth_fields

Revision ID: 43409e6d8208
Revises: l7m8n9o0p1q2
Create Date: 2026-08-19 15:49:16.941219

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '43409e6d8208'
down_revision: Union[str, Sequence[str], None] = 'l7m8n9o0p1q2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add google_oauth_encrypted and microsoft_oauth_encrypted to user_integrations."""
    op.add_column('user_integrations', sa.Column('google_oauth_encrypted', sa.Text(), nullable=True))
    op.add_column('user_integrations', sa.Column('microsoft_oauth_encrypted', sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove google_oauth_encrypted and microsoft_oauth_encrypted from user_integrations."""
    op.drop_column('user_integrations', 'microsoft_oauth_encrypted')
    op.drop_column('user_integrations', 'google_oauth_encrypted')
