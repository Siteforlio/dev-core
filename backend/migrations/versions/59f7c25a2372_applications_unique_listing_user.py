"""applications_unique_listing_user

Revision ID: 59f7c25a2372
Revises: d2094363371c
Create Date: 2026-04-11 20:03:16.874630

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '59f7c25a2372'
down_revision: Union[str, Sequence[str], None] = 'd2094363371c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_applications_listing_user",
        "applications",
        ["job_listing_id", "user_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_applications_listing_user", "applications", type_="unique")
