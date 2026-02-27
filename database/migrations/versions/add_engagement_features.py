"""add engagement features (streak, badges)

Revision ID: engage001
Revises: salesowners001
Create Date: 2026-02-27

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'engage001'
down_revision = 'salesowners001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Streak tracking on users
    op.add_column('users', sa.Column('streak_days', sa.Integer(), server_default='0', nullable=True))
    op.add_column('users', sa.Column('best_streak', sa.Integer(), server_default='0', nullable=True))
    op.add_column('users', sa.Column('last_streak_date', sa.Date(), nullable=True))

    # Badges earned by user — JSON list e.g. ["starter", "motivated", "graduate"]
    op.add_column('users', sa.Column('badges', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'badges')
    op.drop_column('users', 'last_streak_date')
    op.drop_column('users', 'best_streak')
    op.drop_column('users', 'streak_days')
