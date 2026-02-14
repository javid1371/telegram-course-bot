"""add bot text overrides and lesson deadlines

Revision ID: textdead001
Revises: multicourse001
Create Date: 2026-02-14

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'textdead001'
down_revision = 'multicourse001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create bot_texts table for admin text overrides
    op.create_table(
        'bot_texts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('category', 'key', name='uq_bot_texts_category_key'),
    )
    op.create_index(op.f('ix_bot_texts_category'), 'bot_texts', ['category'], unique=False)

    # Add view_deadline_hours to lessons
    op.add_column('lessons', sa.Column('view_deadline_hours', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('lessons', 'view_deadline_hours')
    op.drop_index(op.f('ix_bot_texts_category'), table_name='bot_texts')
    op.drop_table('bot_texts')
