"""add guest support to plans and payment sessions

Revision ID: e729d375d5ac
Revises: d86ff6a86132
Create Date: 2026-03-24 17:57:20.909954

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e729d375d5ac'
down_revision: Union[str, None] = 'd86ff6a86132'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add guest_id support to plans and payment_sessions tables.
    
    Changes:
    1. Add guest_id column to plans (nullable VARCHAR)
    2. Add guest_id column to payment_sessions (nullable VARCHAR)
    3. Make payment_sessions.user_id nullable (was NOT NULL)
    4. Add indexes on guest_id columns
    5. Update existing NULL records with placeholder guest_id
    6. Add check constraints: user_id OR guest_id must be present (NOT VALID for existing data)
    
    This enables guest users to create plans and make payments before signup.
    """
    # Add guest_id to plans table
    op.add_column('plans', sa.Column('guest_id', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_plans_guest_id'), 'plans', ['guest_id'], unique=False)
    
    # Add guest_id to payment_sessions table
    op.add_column('payment_sessions', sa.Column('guest_id', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_payment_sessions_guest_id'), 'payment_sessions', ['guest_id'], unique=False)
    
    # Make payment_sessions.user_id nullable (allows guest payments)
    op.alter_column('payment_sessions', 'user_id',
                    existing_type=sa.UUID(),
                    nullable=True)
    
    # Update existing records where BOTH user_id AND guest_id are NULL
    # Set a placeholder guest_id so check constraint won't fail
    # This handles legacy ETAP 1 plans created before auth was implemented
    from sqlalchemy import text
    op.execute(text("""
        UPDATE plans 
        SET guest_id = 'legacy_' || id::text 
        WHERE user_id IS NULL AND guest_id IS NULL
    """))
    
    op.execute(text("""
        UPDATE payment_sessions 
        SET guest_id = 'legacy_' || id::text 
        WHERE user_id IS NULL AND guest_id IS NULL
    """))
    
    # Add check constraints to ensure either user_id OR guest_id is present
    # Use NOT VALID initially to skip validation of existing rows, then validate
    # Note: Constraint names must be unique across database
    op.execute(text("""
        ALTER TABLE plans 
        ADD CONSTRAINT ck_plans_owner_id 
        CHECK (user_id IS NOT NULL OR guest_id IS NOT NULL) NOT VALID
    """))
    op.execute(text("ALTER TABLE plans VALIDATE CONSTRAINT ck_plans_owner_id"))
    
    op.execute(text("""
        ALTER TABLE payment_sessions 
        ADD CONSTRAINT ck_payment_sessions_owner_id 
        CHECK (user_id IS NOT NULL OR guest_id IS NOT NULL) NOT VALID
    """))
    op.execute(text("ALTER TABLE payment_sessions VALIDATE CONSTRAINT ck_payment_sessions_owner_id"))


def downgrade() -> None:
    """
    Rollback guest support - remove guest_id columns and constraints.
    
    WARNING: This will fail if any guest_id values exist in database.
    Must clean up guest records before downgrade.
    """
    # Drop check constraints
    op.drop_constraint('ck_payment_sessions_owner_id', 'payment_sessions', type_='check')
    op.drop_constraint('ck_plans_owner_id', 'plans', type_='check')
    
    # Make payment_sessions.user_id NOT NULL again
    op.alter_column('payment_sessions', 'user_id',
                    existing_type=sa.UUID(),
                    nullable=False)
    
    # Drop guest_id from payment_sessions
    op.drop_index(op.f('ix_payment_sessions_guest_id'), table_name='payment_sessions')
    op.drop_column('payment_sessions', 'guest_id')
    
    # Drop guest_id from plans
    op.drop_index(op.f('ix_plans_guest_id'), table_name='plans')
    op.drop_column('plans', 'guest_id')
