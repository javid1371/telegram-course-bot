"""add fast track support

Revision ID: fasttrack001
Revises: twospeed001
Create Date: 2026-02-15

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'fasttrack001'
down_revision = 'twospeed001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add fast track fields to courses
    op.add_column('courses', sa.Column('allow_fast_track', sa.Boolean(), server_default='false', nullable=True))
    op.add_column('courses', sa.Column('fast_track_delay', sa.Integer(), server_default='5', nullable=True))

    # Add fast_track_courses JSON to users
    op.add_column('users', sa.Column('fast_track_courses', sa.JSON(), nullable=True, server_default='{}'))


def downgrade() -> None:
    op.drop_column('users', 'fast_track_courses')
    op.drop_column('courses', 'fast_track_delay')
    op.drop_column('courses', 'allow_fast_track')
