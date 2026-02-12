"""Initial schema - plans and plan_versions tables

Revision ID: 360e3cae0377
Revises: 
Create Date: 2026-02-12 10:59:25.512918

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '360e3cae0377'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create plans table
    op.create_table(
        'plans',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('location', sa.String(), nullable=False),
        sa.Column('group_type', sa.String(), nullable=False),
        sa.Column('days_count', sa.Integer(), nullable=False),
        sa.Column('budget_level', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('trip_metadata', postgresql.JSON(astext_type=sa.Text()), nullable=False),
    )
    
    # Create plan_versions table
    op.create_table(
        'plan_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('plans.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('change_type', sa.String(), nullable=False),
        sa.Column('parent_version_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('plan_versions.id'), nullable=True),
        sa.Column('days_json', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('change_summary', sa.Text(), nullable=True),
        sa.UniqueConstraint('plan_id', 'version_number', name='uq_plan_version'),
    )
    
    # Create indexes for performance
    op.create_index('ix_plan_versions_plan_id', 'plan_versions', ['plan_id'])
    op.create_index('ix_plan_versions_version_number', 'plan_versions', ['version_number'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_plan_versions_version_number', table_name='plan_versions')
    op.drop_index('ix_plan_versions_plan_id', table_name='plan_versions')
    
    # Drop tables (order matters due to foreign keys)
    op.drop_table('plan_versions')
    op.drop_table('plans')
