"""Add is_shadow column to users for cross-platform shadow profiles

Revision ID: shadowuser001
Revises: crosssync001
Create Date: 2026-02-25
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'shadowuser001'
down_revision = 'crosssync001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_shadow column — defaults to False for all existing users
    op.add_column(
        'users',
        sa.Column('is_shadow', sa.Boolean(), server_default=sa.text('false'), nullable=False)
    )
    op.create_index('ix_users_is_shadow', 'users', ['is_shadow'])

    # Replace the old unique constraint with a partial unique index
    # that excludes shadow users (telegram_user_id=0)
    op.drop_constraint('uq_user_platform', 'users', type_='unique')
    op.create_index(
        'uq_user_platform_active',
        'users',
        ['telegram_user_id', 'platform'],
        unique=True,
        postgresql_where=sa.text('is_shadow = false'),
    )


def downgrade() -> None:
    op.drop_index('uq_user_platform_active', table_name='users')
    op.create_unique_constraint('uq_user_platform', 'users', ['telegram_user_id', 'platform'])
    op.drop_index('ix_users_is_shadow', table_name='users')
    op.drop_column('users', 'is_shadow')
