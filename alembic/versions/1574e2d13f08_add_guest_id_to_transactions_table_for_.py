"""Add guest_id to transactions table for guest checkout support

Revision ID: 1574e2d13f08
Revises: e729d375d5ac
Create Date: 2026-03-27 08:32:18.379371

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1574e2d13f08'
down_revision: Union[str, None] = 'e729d375d5ac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add guest_id column (nullable)
    op.add_column('transactions', sa.Column('guest_id', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_transactions_guest_id'), 'transactions', ['guest_id'], unique=False)
    
    # Make user_id nullable (was nullable=False before)
    op.alter_column('transactions', 'user_id',
               existing_type=sa.UUID(),
               nullable=True)
    
    # Add CHECK constraint: user_id XOR guest_id
    op.create_check_constraint(
        'transactions_owner_check',
        'transactions',
        '(user_id IS NOT NULL AND guest_id IS NULL) OR (user_id IS NULL AND guest_id IS NOT NULL)'
    )


def downgrade() -> None:
    # Drop CHECK constraint
    op.drop_constraint('transactions_owner_check', 'transactions', type_='check')
    
    # Make user_id NOT NULL again
    # WARNING: This will fail if there are transactions with guest_id!
    # In production, you would need to handle existing guest transactions
    op.alter_column('transactions', 'user_id',
               existing_type=sa.UUID(),
               nullable=False)
    
    # Drop guest_id column
    op.drop_index(op.f('ix_transactions_guest_id'), table_name='transactions')
    op.drop_column('transactions', 'guest_id')
