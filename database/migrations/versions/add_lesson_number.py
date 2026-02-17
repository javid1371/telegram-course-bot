"""add lesson_number field

Revision ID: add_lesson_number
Revises: add_media_library
Create Date: 2026-02-17
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'add_lesson_number'
down_revision = 'add_media_library'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('lessons', sa.Column('lesson_number', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('lessons', 'lesson_number')
