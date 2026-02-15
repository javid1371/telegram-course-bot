"""add webhook failed events queue

Revision ID: webhookqueue001
Revises: fasttrack001
Create Date: 2025-02-12

Adds webhook_failed_events table for reliable webhook delivery
with exponential backoff retry.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'webhookqueue001'
down_revision = 'fasttrack001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'webhook_failed_events',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('event_id', sa.String(50), nullable=False, index=True),
        sa.Column('webhook_id', sa.Integer(), nullable=False, index=True),
        sa.Column('webhook_name', sa.String(100), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('error_message', sa.Text()),
        sa.Column('retry_count', sa.Integer(), server_default='0'),
        sa.Column('next_retry_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table('webhook_failed_events')
