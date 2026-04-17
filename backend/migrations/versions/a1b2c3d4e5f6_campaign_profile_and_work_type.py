"""campaign_profile_and_work_type

Revision ID: a1b2c3d4e5f6
Revises: 36b86f36ceba
Create Date: 2026-04-14 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '36b86f36ceba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add work_type + anywhere to campaigns
    op.add_column('job_hunter_campaigns', sa.Column('anywhere', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('job_hunter_campaigns', sa.Column('work_type', sa.String(20), nullable=False, server_default='remote'))

    # Create campaign_profiles table
    op.create_table(
        'campaign_profiles',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('campaign_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('country', sa.String(100), nullable=True),
        sa.Column('linkedin_url', sa.String(), nullable=True),
        sa.Column('github_url', sa.String(), nullable=True),
        sa.Column('portfolio_url', sa.String(), nullable=True),
        sa.Column('work_experience', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('education', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('skills', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('projects', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('languages_spoken', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('achievements', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('raw_context', sa.Text(), nullable=True),
        sa.Column('is_complete', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('completion_gaps', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['campaign_id'], ['job_hunter_campaigns.id'],
                                name=op.f('fk_campaign_profiles_campaign_id')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'],
                                name=op.f('fk_campaign_profiles_user_id')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_campaign_profiles')),
        sa.UniqueConstraint('campaign_id', name=op.f('uq_campaign_profiles_campaign_id')),
    )
    op.create_index('ix_campaign_profiles_campaign', 'campaign_profiles', ['campaign_id'])
    op.create_index('ix_campaign_profiles_user', 'campaign_profiles', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_campaign_profiles_user', table_name='campaign_profiles')
    op.drop_index('ix_campaign_profiles_campaign', table_name='campaign_profiles')
    op.drop_table('campaign_profiles')
    op.drop_column('job_hunter_campaigns', 'work_type')
    op.drop_column('job_hunter_campaigns', 'anywhere')
