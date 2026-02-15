"""add 2x speed support

Revision ID: twospeed001
Revises: textoverrides001
Create Date: 2026-02-15

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'twospeed001'
down_revision = 'textoverrides001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add allow_2x to courses
    op.add_column('courses', sa.Column('allow_2x', sa.Boolean(), server_default='false', nullable=True))

    # Add double_speed_courses JSON to users
    op.add_column('users', sa.Column('double_speed_courses', sa.JSON(), nullable=True, server_default='{}'))


def downgrade() -> None:
    op.drop_column('users', 'double_speed_courses')
    op.drop_column('courses', 'allow_2x')
