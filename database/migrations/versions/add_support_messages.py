"""add support messages table

Revision ID: supportchat001
Revises: engage001
Create Date: 2026-03-14

Adds support_messages table for bidirectional user-admin chat.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'supportchat001'
down_revision = 'engage001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'support_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sender_type', sa.String(length=20), nullable=False),
        sa.Column('message_text', sa.Text(), nullable=True),
        sa.Column('file_id', sa.String(length=500), nullable=True),
        sa.Column('file_type', sa.String(length=50), nullable=True),
        sa.Column('platform', sa.String(length=20), nullable=False),
        sa.Column('is_read', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_support_messages_user_id'), 'support_messages', ['user_id'], unique=False)
    op.create_index(op.f('ix_support_messages_platform'), 'support_messages', ['platform'], unique=False)
    op.create_index(op.f('ix_support_messages_is_read'), 'support_messages', ['is_read'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_support_messages_is_read'), table_name='support_messages')
    op.drop_index(op.f('ix_support_messages_platform'), table_name='support_messages')
    op.drop_index(op.f('ix_support_messages_user_id'), table_name='support_messages')
    op.drop_table('support_messages')
